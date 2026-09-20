from types import SimpleNamespace

from workflows import Workflow


class CookingHarness(Workflow):
    """Recorded state transitions; no native controller or game input."""
    def __init__(self, *, missing=(), busy=False, policy=None):
        super().__init__(SimpleNamespace(
            tasker=SimpleNamespace(stopping=False),
            get_node_object=lambda name: SimpleNamespace(attach=policy or {})))
        self.actions = []
        self.messages = []
        self.missing = missing
        self.busy = busy
        self.selected = None

    def navigate(self, target):
        pass

    def frame(self):
        return object()

    def act(self, node):
        self.actions.append(node)
        if node.startswith("HomeCookingChoose"):
            self.selected = node.removeprefix("HomeCookingChoose")

    def reco(self, node, image):
        if node == "HomeCookingIdle":
            return not self.busy
        if node == "HomeCookingDone":
            return False
        if node == "HomeCookingQueue":
            return self.busy
        if node == "HomeCookingInsufficient":
            return self.selected in self.missing
        return True

    def wait_for(self, nodes, timeout=10):
        return nodes[0], None

    def counter(self, node, image=None):
        return (4, 4) if node == "HomeCookingQueue" else (28, 24)

    def log(self, message):
        self.messages.append(message)

    def collect(self):
        self.actions.append("CollectCompletedFood")


def test_missing_first_candidate_falls_back_then_collects():
    w = CookingHarness(missing=("Cookie",))
    w.cook()
    assert w.actions.index("HomeCookingChooseCookie") < w.actions.index("HomeCookingChoosePopcorn")
    assert w.actions.index("HomeCookingMax") < w.actions.index("HomeCookingStart")
    assert w.actions[-1] == "CollectCompletedFood"


def test_all_candidates_missing_does_not_start_production():
    w = CookingHarness(missing=("Cookie", "Popcorn"))
    w.cook()
    assert "HomeCookingStart" not in w.actions
    assert "CollectCompletedFood" not in w.actions


def test_existing_queue_is_not_modified():
    w = CookingHarness(busy=True)
    w.cook()
    assert "HomeCookingAll" not in w.actions
    assert "HomeCookingStart" not in w.actions
    assert w.actions[-1] == "CollectCompletedFood"


def test_single_portion_and_disabled_candidate_are_respected():
    w = CookingHarness(policy={"Cookie": False})
    w.cook(maximum=False)
    assert "HomeCookingChooseCookie" not in w.actions
    assert "HomeCookingMin" in w.actions
    assert "HomeCookingMax" not in w.actions


def test_unreadable_queue_does_not_start_another_recipe():
    import pytest

    w = CookingHarness()
    w.reco = lambda *args: False
    with pytest.raises(RuntimeError, match="烹饪槽状态"):
        w.cook()
    assert "HomeCookingStart" not in w.actions


def test_finished_queue_is_collected_when_counter_is_unreadable():
    w = CookingHarness(busy=True)
    w.reco = lambda node, image: node == "HomeCookingDone"
    w.counter = lambda *args: (_ for _ in ()).throw(AssertionError("Unreadable counter"))
    w.cook()
    assert w.actions[-1] == "CollectCompletedFood"
    assert "HomeCookingStart" not in w.actions
