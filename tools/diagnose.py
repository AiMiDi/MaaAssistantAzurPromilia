"""Read-only Win32 capture probe for the real MaaFramework controller."""
import argparse
import json
from pathlib import Path

from PIL import Image
from maa.controller import Win32Controller
from maa.define import MaaWin32InputMethodEnum, MaaWin32ScreencapMethodEnum
from maa.toolkit import Toolkit

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--method", default="FramePool", choices=["FramePool", "PrintWindow", "ScreenDC", "DXGI_DesktopDup_Window"])
    parser.add_argument("--output", default=str(ROOT / "debug" / "capture.png"))
    args = parser.parse_args()
    Toolkit.init_option(ROOT / "debug", {"logging": True, "stdout_level": 2})
    windows = [w for w in Toolkit.find_desktop_windows() if w.window_name == "AzurPromilia"]
    print(json.dumps([{"hwnd": w.hwnd, "class": w.class_name, "title": w.window_name} for w in windows], ensure_ascii=False), flush=True)
    if len(windows) != 1:
        raise SystemExit("Expected exactly one running AzurPromilia game window.")
    controller = Win32Controller(windows[0].hwnd, getattr(MaaWin32ScreencapMethodEnum, args.method), MaaWin32InputMethodEnum.Seize, MaaWin32InputMethodEnum.Seize)
    connected = controller.post_connection().wait().succeeded
    print(f"connection={connected}", flush=True)
    if not connected:
        raise SystemExit(2)
    captured = controller.post_screencap().wait().succeeded
    print(f"capture={captured}", flush=True)
    if not captured:
        raise SystemExit(3)
    img = controller.cached_image
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(img[:, :, ::-1]).save(output)
    print(json.dumps({"shape": list(img.shape), "std": float(img.std()), "path": str(output)}, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
