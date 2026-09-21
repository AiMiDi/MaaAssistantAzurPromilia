"""Verify update recognition against a supplied crop using a fake controller only."""
import argparse
import json
from pathlib import Path
import sys

import numpy as np
from PIL import Image
from maa.controller import CustomController
from maa.resource import Resource
from maa.tasker import Tasker

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "agent"))
from workflows import register


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("image", help="Crop containing the full resource update dialog")
    args = parser.parse_args()
    source = Image.open(args.image).convert("RGB")
    source = source.resize((1280, round(source.height * 1280 / source.width)))
    canvas = Image.new("RGB", (1280, 720), (100, 100, 100))
    canvas.paste(source, (0, 160))
    image = np.array(canvas)[:, :, ::-1].copy()
    methods = {name: (lambda self, *args: True) for name in (
        "connect", "start_app", "stop_app", "swipe", "touch_down", "touch_move",
        "touch_up", "click_key", "input_text", "key_down", "key_up")}
    methods.update({"request_uuid": lambda self: "offline-update-replay",
                    "get_features": lambda self: 0,
                    "screencap": lambda self: self.image.copy(),
                    "click": lambda self, x, y: self.clicks.append([x, y]) is None})
    replay = type("Replay", (CustomController,), methods)
    resource = Resource()
    register(resource)
    assert resource.post_bundle(ROOT / "assets/resource").wait().succeeded
    results = []
    for negative in (False, True):
        controller = replay()
        controller.image = image.copy()
        controller.clicks = []
        if negative:
            # Remove only the update message, leaving the Confirm button visible.
            controller.image[295:380, 200:1080, :] = 240
        assert controller.post_connection().wait().succeeded
        tasker = Tasker()
        tasker.bind(resource, controller)
        job = tasker.post_task("ConfirmGameUpdate", {"ConfirmGameUpdate": {
            "timeout": 1000, "post_delay": 0}}).wait()
        results.append({"message_present": not negative, "succeeded": job.succeeded,
                        "simulated_clicks": controller.clicks})
        if negative:
            assert not job.succeeded and not controller.clicks
        else:
            assert job.succeeded and len(controller.clicks) == 1 and controller.clicks[0][0] > 900
    print(json.dumps(results, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
