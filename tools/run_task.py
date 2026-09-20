"""Run a MaaFramework pipeline, or inspect a screenshot without sending input."""
import argparse
import json
import sys
import time
from pathlib import Path

from PIL import Image
from maa.controller import Win32Controller
from maa.define import MaaWin32InputMethodEnum, MaaWin32ScreencapMethodEnum
from maa.resource import Resource
from maa.tasker import Tasker
from maa.toolkit import Toolkit

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "agent"))
from workflows import register


def wait(job, seconds, tasker=None):
    deadline = time.monotonic() + seconds
    while not job.done:
        if time.monotonic() >= deadline:
            if tasker:
                tasker.post_stop()
            raise TimeoutError(f"Operation exceeded {seconds}s")
        time.sleep(0.1)
    return job


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--entry")
    mode.add_argument("--inspect", action="store_true")
    parser.add_argument("--method", default="FramePool", choices=["FramePool", "PrintWindow", "ScreenDC", "DXGI_DesktopDup_Window"])
    parser.add_argument("--input", default="Seize", choices=["Seize", "PostMessage", "PostMessageWithCursorPos"])
    parser.add_argument("--timeout", type=float, default=270)
    parser.add_argument("--output", default=str(ROOT / "debug" / "last.png"))
    args = parser.parse_args()
    Toolkit.init_option(ROOT / "debug", {"logging": True, "stdout_level": 2})
    resource = Resource()
    register(resource)
    if not wait(resource.post_bundle(ROOT / "assets" / "resource"), 30).succeeded:
        raise RuntimeError("Resource load failed. Run setup.ps1 to install OCR models.")
    windows = [w for w in Toolkit.find_desktop_windows() if w.window_name == "AzurPromilia" and w.class_name == "UnityWndClass"]
    if len(windows) != 1:
        raise RuntimeError(f"Expected one AzurPromilia Unity window; found {len(windows)}")
    controller = Win32Controller(windows[0].hwnd, getattr(MaaWin32ScreencapMethodEnum, args.method), getattr(MaaWin32InputMethodEnum, args.input), getattr(MaaWin32InputMethodEnum, args.input))
    controller.set_screenshot_target_short_side(720)
    tasker = Tasker()
    tasker.bind(resource, controller)
    if not wait(controller.post_connection(), 30, tasker).succeeded:
        raise RuntimeError("Game connection failed")
    if not wait(controller.post_screencap(), 15, tasker).succeeded:
        raise RuntimeError("Game capture failed")
    img = controller.cached_image
    if img.shape[:2] != (720, 1280) or img.std() < 3:
        raise RuntimeError("Expected a nonblank 16:9 game frame. Change the game to 1280x720 or 1920x1080.")
    entry = "InspectScreen" if args.inspect else args.entry
    override = {"InspectScreen": {"recognition": "OCR", "action": "DoNothing"}} if args.inspect else {}
    try:
        job = wait(tasker.post_task(entry, override), args.timeout, tasker)
        detail = job.get()
        print(json.dumps({"entry": entry, "succeeded": job.succeeded, "nodes": [{"name": n.name, "completed": n.completed, "recognition": n.recognition.raw_detail if n.recognition else None} for n in detail.nodes] if detail else []}, ensure_ascii=False, indent=2), flush=True)
        if not wait(controller.post_screencap(), 15, tasker).succeeded:
            raise RuntimeError("Final screenshot failed")
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        Image.fromarray(controller.cached_image[:, :, ::-1]).save(output)
        return 0 if job.succeeded else 1
    except KeyboardInterrupt:
        tasker.post_stop().wait()
        return 130
    finally:
        wait(controller.post_inactive(), 10)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (RuntimeError, TimeoutError) as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(2)
