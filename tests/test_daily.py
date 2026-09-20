from types import SimpleNamespace

import pytest

from workflows import Workflow


class DailyHarness(Workflow):
    def __init__(self, *, pending=False, chest=False, bottom=True):
        super().__init__(SimpleNamespace(tasker=SimpleNamespace(stopping=False)))
        self.actions = []
        self.page = 0
        self.pending = pending
        self.chest = chest
        self.bottom = bottom
        self.verified = False

    def navigate(self, target):
        pass

    def frame(self):
        return object()

    def act(self, node):
        self.actions.append(node)
        if node == "DailyScroll":
            self.page += 1
        elif node == "DailyScrollUp":
            self.page = 0
        elif node == "DailyClaim":
            self.pending = False
        elif node == "DailyChest20":
            self.chest = False

    def reco(self, node, image):
        if node == "DailyActive":
            return True
        if node == "DailyClaim" and self.pending and self.page == 1:
            return SimpleNamespace(box=SimpleNamespace(y=300))
        if node == "DailyAtBottom":
            return self.bottom and self.page >= 3
        if node == "DailyChest20":
            return self.chest
        # A false-positive marker alone must not open an unearned chest.
        if node == "DailyChest40":
            return True
        return None

    def wait_for(self, nodes, timeout=10):
        return nodes[0], None

    def activity(self, image):
        return 20

    def row_text(self, image, box):
        return "每日登录"

    def verify_daily_claim(self, before, title, box):
        self.verified = True

    def log(self, message):
        pass


def test_empty_daily_list_is_scanned_to_bottom_without_claiming():
    w = DailyHarness()
    w.daily()
    assert w.actions.count("DailyScroll") == 3
    assert "DailyClaim" not in w.actions
    assert not any(node.startswith("DailyChest") for node in w.actions)
    assert w.actions[-1] == "CloseDaily"


def test_claim_is_verified_and_rescans_reordered_list_before_chests():
    w = DailyHarness(pending=True, chest=True)
    w.daily()
    assert w.verified
    assert w.actions.count("DailyScrollUp") == 2
    assert w.actions.count("DailyClaim") == 1
    assert w.actions.count("DailyChest20") == 1
    assert "DailyChest40" not in w.actions
    assert "RewardPopup" in w.actions


def test_missing_bottom_stops_instead_of_reporting_success():
    w = DailyHarness(bottom=False)
    with pytest.raises(RuntimeError, match="列表底部"):
        w.daily()
    assert w.actions.count("DailyScroll") == 16
    assert "CloseDaily" not in w.actions


@pytest.mark.parametrize("before,after,claimed,success", [
    (0, 20, False, True),
    (20, 20, False, False),
    (100, 100, False, False),
    (100, 100, True, True),
])
def test_claim_verification_requires_a_game_state_change(monkeypatch, before, after, claimed, success):
    clock = iter(range(100))
    monkeypatch.setattr("workflows.time.monotonic", lambda: next(clock))
    monkeypatch.setattr("workflows.time.sleep", lambda _: None)
    w = Workflow(SimpleNamespace(
        tasker=SimpleNamespace(stopping=False),
        run_recognition=lambda *args: SimpleNamespace(hit=claimed)))
    w.frame = lambda: object()
    w.reco = lambda *args: True
    w.activity = lambda image: after
    w.row_text = lambda *args: "每日登录"
    if success:
        w.verify_daily_claim(before, "每日登录", SimpleNamespace(y=300))
    else:
        with pytest.raises(RuntimeError, match="未观察到"):
            w.verify_daily_claim(before, "每日登录", SimpleNamespace(y=300))
