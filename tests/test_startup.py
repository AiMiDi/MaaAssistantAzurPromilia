from types import SimpleNamespace
import numpy as np
import pytest
from workflows import Workflow, SupportedStartupFrame


def test_text_dialog_guard_allows_ultrawide_but_rejects_black():
    image = np.zeros((720, 1720, 3), dtype=np.uint8)
    guard = SupportedStartupFrame()
    assert guard.analyze(None, SimpleNamespace(image=image)).box is None
    image[:, :500] = 200
    assert guard.analyze(None, SimpleNamespace(image=image)).box is not None


def test_startup_confirms_specific_update_then_enters(monkeypatch):
    w = Workflow(SimpleNamespace(tasker=SimpleNamespace(stopping=False)))
    image = np.zeros((720, 1280, 3), dtype=np.uint8)
    image[:, :500] = 200
    states = iter(["ConfirmGameUpdate", "StartGame", "HomeHud"])
    state = {"page": None}
    def frame(startup=False):
        state["page"] = next(states)
        return image
    w.frame = frame
    w.reco = lambda node, image: node == state["page"]
    actions = []
    w.act = actions.append
    w.log = lambda message: None
    monkeypatch.setattr("workflows.time.sleep", lambda duration: None)
    w.startup()
    assert actions == ["ConfirmGameUpdate", "StartGame"]


def test_repeated_update_is_bounded(monkeypatch):
    w = Workflow(SimpleNamespace(tasker=SimpleNamespace(stopping=False)))
    w.frame = lambda startup=False: object()
    w.reco = lambda node, image: node == "ConfirmGameUpdate"
    actions = []
    w.act = actions.append
    w.log = lambda message: None
    monkeypatch.setattr("workflows.time.sleep", lambda duration: None)
    with pytest.raises(RuntimeError, match="重复"):
        w.startup()
    assert len(actions) == 3
