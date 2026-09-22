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
        if node == "DailyClaim" and self.pending and self.page == 0:
            return SimpleNamespace(box=SimpleNamespace(y=300))
        if node == "DailyStoppedRow":
            return self.bottom
        if node == "DailyChest20":
            return self.chest
        # A false-positive marker alone must not open an unearned chest.
        if node == "DailyChest40":
            return True
        return None

    def wait_for(self, nodes, timeout=10):
        return nodes[0], None

    def activity(self, image, weekly=False):
        return 20

    def row_text(self, image, box):
        return "每日登录"

    def verify_daily_claim(self, before, title, box, weekly=False):
        self.verified = True

    def log(self, message):
        pass


def test_sorted_daily_list_stops_without_scrolling():
    w = DailyHarness()
    w.daily()
    assert "DailyScroll" not in w.actions
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


def test_unknown_task_state_stops_instead_of_reporting_success():
    w = DailyHarness(bottom=False)
    with pytest.raises(RuntimeError, match="首屏任务状态"):
        w.daily()
    assert "DailyScroll" not in w.actions
    assert "CloseDaily" not in w.actions


@pytest.mark.parametrize('text,expected',[('0/100',0),('20 / 100',20),('100',100)])
def test_activity_accepts_complete_counter(text,expected):
    w=Workflow(SimpleNamespace(tasker=SimpleNamespace(stopping=False)))
    w.reco=lambda *args:SimpleNamespace(best_result=SimpleNamespace(text=text))
    assert w.activity(object())==expected


def test_activity_reads_large_zero_left_of_detected_label():
    def recognize(node,image,override):
        if node=='DailyActivityLabel':
            return SimpleNamespace(hit=True,best_result=SimpleNamespace(box=[276,639,36,15]))
        assert override[node]['roi']==[239,636,33,40]
        assert override[node]['only_rec'] is True
        return SimpleNamespace(hit=True,best_result=SimpleNamespace(text='0'))
    w=Workflow(SimpleNamespace(tasker=SimpleNamespace(stopping=False),run_recognition=recognize))
    w.reco=lambda *args:None
    assert w.activity(object())==0


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


def test_weekly_uses_its_own_guards_and_claims_earned_chest():
    w=DailyHarness(pending=True,chest=True)
    original_reco, original_act = w.reco, w.act
    seen=[]
    w.reco=lambda node,image:original_reco(node.replace('Weekly','Daily'),image)
    def act(node):
        seen.append(node)
        original_act(node.replace('Weekly','Daily'))
    w.act=act
    w.daily(weekly=True)
    assert 'WeeklySelectTab' in seen
    assert seen.count('WeeklyClaim')==1
    assert seen.count('WeeklyChest20')==1
    assert 'WeeklyChest40' not in seen
    assert 'DailyScroll' not in seen
