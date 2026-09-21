"""PI pretask: launch the PC game before MFA connects its Win32 controller."""
import csv
import ctypes
import json
import os
from pathlib import Path
import subprocess
import sys
import time

from window import find_game_windows

DEFAULT_PATH = r"E:\AzurPromilia bilibili"


def game_windows():
    return find_game_windows(ctypes.WinDLL("user32", use_last_error=True))


def game_running():
    result = subprocess.run(
        ["tasklist.exe", "/FI", "IMAGENAME eq AzurPromilia.exe", "/FO", "CSV", "/NH"],
        capture_output=True, timeout=10, creationflags=subprocess.CREATE_NO_WINDOW, check=True)
    # Only the ASCII executable name is needed; localized status text is ignored.
    return any(row and row[0].lower() == "azurpromilia.exe"
               for row in csv.reader(result.stdout.decode("utf-8", errors="replace").splitlines()))


def launch_process(path):
    from official_launcher import start_official
    start_official(path)


def resolve_path(value):
    value = value.strip().strip('"')
    if not value:
        raise ValueError("请设置游戏安装路径")
    path = Path(os.path.expandvars(value)).expanduser()
    if path.name.lower() == "azurpromilia.exe":
        path = path.parent.parent
    if path.is_dir():
        import re
        versions = [p for p in path.iterdir() if p.is_dir() and re.fullmatch(r"\d+(?:\.\d+)+", p.name)]
        versions.sort(key=lambda p: tuple(map(int, p.name.split('.'))), reverse=True)
        candidates = [path / "launcher.exe"] + [p / "launcher.exe" for p in versions]
        path = next((candidate for candidate in candidates if candidate.is_file()), candidates[0])
    if path.name.lower() != "launcher.exe" or not path.is_file():
        raise ValueError("未找到官方 launcher.exe，请选择安装目录或官方启动器路径")
    return path.resolve()


def ensure_game(options, *, windows=game_windows, running=game_running,
                spawn=launch_process, clock=time.monotonic, sleep=time.sleep, log=print):
    mode = options.get("GameLaunch", "On")
    if mode not in ("On", "Off"):
        raise ValueError("未知启动策略")
    if mode == "Off":
        log("自动启动已关闭，使用手动打开的游戏")
        return "disabled"
    found = windows()
    if len(found) > 1:
        raise RuntimeError("发现多个游戏窗口，请保留一个后重试")
    if found:
        log("游戏已运行，复用现有窗口")
        return "existing"
    timeout = int(options.get("GameLaunchTimeout", {}).get("seconds", "120"))
    if not 10 <= timeout <= 600:
        raise ValueError("启动等待时间必须为 10～600 秒")
    process = None
    if running():
        log("游戏进程正在启动，等待窗口，不重复启动")
    else:
        path = resolve_path(options.get("GameLaunchPath", {}).get("path", DEFAULT_PATH))
        process = spawn(path)
        log("游戏启动请求已发送，等待窗口")
    deadline = clock() + timeout
    while clock() < deadline:
        found = windows()
        if len(found) > 1:
            raise RuntimeError("启动后出现多个游戏窗口，停止连接")
        if found:
            log("游戏窗口已就绪，继续连接")
            return "ready"
        if process is not None and process.poll() is not None:
            # Some launch stubs hand off to another game process.
            if not running():
                raise RuntimeError("游戏进程在窗口出现前退出，请手动检查更新或登录状态")
            process = None
        sleep(0.5)
    raise TimeoutError("等待游戏窗口超时；游戏进程保留，请检查启动器、更新或登录提示")


def main():
    log_file = Path(__file__).resolve().parents[1] / "debug/launcher.log"
    log_file.parent.mkdir(parents=True, exist_ok=True)

    def report(message):
        with log_file.open("a", encoding="utf-8") as stream:
            stream.write(time.strftime("%Y-%m-%d %H:%M:%S ") + message + "\n")
        print(message, flush=True)

    try:
        options = json.loads(sys.argv[1]) if len(sys.argv) > 1 else {}
        if not isinstance(options, dict):
            raise ValueError("启动配置必须为 JSON 对象")
        ensure_game(options, log=report)
        return 0
    except Exception as exc:
        report("启动失败：" + str(exc))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
