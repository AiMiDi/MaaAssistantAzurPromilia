import json
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from workflows import SupportedFrame, Workflow, parse_counter, recipe_order, supported_frame


def frame(shape=(720, 1280, 3)):
    image = np.zeros(shape, dtype=np.uint8)
    image[:, :shape[1] // 2] = 200
    return image


@pytest.mark.parametrize("image", [None, np.zeros((720, 1280, 3), dtype=np.uint8),
                                  frame((720, 960, 3)), frame((720, 1720, 3))])
def test_unsupported_frames_cannot_match(image):
    assert supported_frame(image) is False


def test_guard_detail_is_serializable_for_native_callback():
    result = SupportedFrame().analyze(None, SimpleNamespace(image=frame()))
    assert result.box is not None
    assert json.loads(json.dumps(result.detail))["supported_16_9"] is True


@pytest.mark.parametrize("text", ["416", "-1/4", "4/O", "4/6件", "4/6/2"])
def test_ambiguous_inventory_ocr_does_not_become_a_quantity(text):
    assert parse_counter(text) is None


def test_inventory_counter_preserves_order():
    assert parse_counter(" 28 / 24 ") == (28, 24)


def test_recipe_priority_and_exclusions():
    assert recipe_order({}) == ["Cookie"]
    assert recipe_order({"priority": "Popcorn"}) == ["Cookie"]
    assert recipe_order({"Cookie": False}) == ["Cookie"]
    assert recipe_order({"Cookie": False, "Popcorn": False}) == ["Cookie"]
    assert recipe_order({"priority": "Unknown"}) == ["Cookie"]


def test_unknown_page_sends_no_input():
    w = Workflow(SimpleNamespace(tasker=SimpleNamespace(stopping=False)))
    w.frame = lambda: frame()
    w.reco = lambda *args: None
    w.act = lambda node: pytest.fail("Unknown page must not cause input: " + node)
    with pytest.raises(RuntimeError, match="当前页面"):
        w.navigate("MenuPage")


def test_input_nodes_validate_geometry_before_clicking():
    root = Path(__file__).resolve().parents[1]
    nodes = {}
    for path in (root / "assets/resource/pipeline").glob("*.json"):
        nodes.update(json.loads(path.read_text(encoding="utf-8")))
    for name, node in nodes.items():
        if node.get("action") in ("Click", "LongPress", "ClickKey", "LongPressKey", "Scroll"):
            assert node["recognition"] == "And", name
            guard = "SupportedStartupFrame" if name in {"ConfirmGameUpdate", "StartGame"} else "SupportedFrame"
            assert guard in node["all_of"], name
