"""Use the official launcher's visible Start button; never handle authentication."""
import time
from pathlib import Path
import subprocess


def start_official(path):
    from maa.controller import Win32Controller
    from maa.custom_recognition import CustomRecognition
    from maa.define import MaaWin32InputMethodEnum as Input, MaaWin32ScreencapMethodEnum as Capture
    from maa.resource import Resource
    from maa.tasker import Tasker
    from maa.toolkit import Toolkit

    def windows():
        return [w for w in Toolkit.find_desktop_windows()
                if w.window_name == "蓝色星原：旅谣" and w.class_name == "Chrome_WidgetWin_1"]

    def game_ready():
        return any(w.window_name == "AzurPromilia" and w.class_name == "UnityWndClass"
                   for w in Toolkit.find_desktop_windows())

    found = windows()
    if not found:
        subprocess.Popen([str(path), "source=2"], cwd=str(path.parent), shell=False,
                         stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL, creationflags=subprocess.CREATE_NEW_PROCESS_GROUP)
    deadline = time.monotonic() + 45
    while not found and time.monotonic() < deadline:
        time.sleep(0.5)
        found = windows()
    if len(found) != 1:
        raise RuntimeError("未找到唯一的官方启动器窗口")

    class LauncherFrame(CustomRecognition):
        def analyze(self, context, argv):
            image = argv.image
            valid = image is not None and image.shape[:2] == (720, 1185) and image.std() >= 3
            if valid:
                blocked = context.run_recognition("LauncherBlocked", image)
                valid = not (blocked and blocked.hit)
            return self.AnalyzeResult((0, 0, 1185, 720) if valid else None, {})

    root = Path(__file__).resolve().parents[1]
    bundle = root / "resource" if (root / "resource").exists() else root / "assets/resource"
    Tasker.set_log_dir(str(root / "debug"))
    resource = Resource()
    resource.register_custom_recognition("LauncherFrame", LauncherFrame())
    if not resource.post_bundle(bundle).wait().succeeded:
        raise RuntimeError("启动器识别资源加载失败")
    controller = Win32Controller(found[0].hwnd, Capture.FramePool, Input.Seize, Input.Seize)
    controller.set_screenshot_target_short_side(720)
    tasker = Tasker()
    tasker.bind(resource, controller)
    if not controller.post_connection().wait().succeeded:
        raise RuntimeError("无法连接官方启动器")
    nodes = {
        "LauncherFrame": {"recognition": "Custom", "custom_recognition": "LauncherFrame"},
        "LauncherBlocked": {"recognition": "OCR", "expected": ["安全验证", "滑块", "验证码", "扫码登录", "密码登录"]},
        "OfficialStart": {
            "recognition": "And", "all_of": ["LauncherFrame",
                {"recognition": "OCR", "expected": "^启动游戏$", "roi": [825, 610, 250, 70]},
                {"recognition": "OCR", "expected": "当前版本", "roi": [850, 676, 250, 35]}],
            "box_index": 1, "action": "Click", "target": True, "post_delay": 1200,
            "timeout": 15000,
        },
    }
    try:
        job = tasker.post_task("OfficialStart", nodes)
        deadline = time.monotonic() + 20
        while time.monotonic() < deadline:
            if game_ready():
                if not job.done:
                    tasker.post_stop().wait()
                return
            if job.done and job.succeeded:
                return
            # The launcher can close immediately after Start. Its disappearing
            # capture surface is not a failed launch if the game appears next.
            time.sleep(0.1)
        if not job.done:
            tasker.post_stop().wait()
            raise TimeoutError("启动器未准备好，请检查更新、登录或验证提示")
        if not job.succeeded:
            raise RuntimeError("未识别到可用的启动游戏按钮，请手动完成登录或验证后重试")
    finally:
        controller.post_inactive().wait()
