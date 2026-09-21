from types import SimpleNamespace

import pytest

from workflows import Workflow


def harness():
    workflow = Workflow(SimpleNamespace(tasker=SimpleNamespace(stopping=False)))
    workflow.frame = lambda: object()
    workflow.log = lambda message: None
    workflow.navigate = lambda page: None
    workflow.actions = []
    workflow.act = workflow.actions.append
    return workflow


def test_signin_reward_popup_then_stable_page(monkeypatch):
    w = harness()
    observations = iter(['popup', 'page', 'page', 'page'])
    w.frame = lambda: next(observations)
    w.reco = lambda name, state: ((name == 'RewardPopup' and state == 'popup') or
                                  (name == 'SignInPage' and state == 'page'))
    monkeypatch.setattr('workflows.time.sleep', lambda _: None)
    w.wait_signin_settled()
    assert w.actions == ['RewardPopup']


def test_signin_claim_still_visible_is_not_success(monkeypatch):
    w = harness()
    w.reco = lambda name, _: name in ('SignInPage', 'SignInClaimProbe')
    ticks = iter(range(0, 40, 2))
    monkeypatch.setattr('workflows.time.monotonic', lambda: next(ticks))
    monkeypatch.setattr('workflows.time.sleep', lambda _: None)
    with pytest.raises(TimeoutError):
        w.wait_signin_settled()


def test_signin_absent_card_does_not_claim():
    w = harness()
    w.reco = lambda name, _: name == 'SignInPage'
    w.wait_for = lambda *args: ('SignInPage', None)
    w.wait_signin_settled = lambda: None
    w.signin()
    assert 'SignInClaim' not in w.actions
    assert w.actions[-1] == 'CloseSignIn'


def test_ranch_empty_sends_no_click():
    w = harness()
    w.reco = lambda *args: None
    w.collect_ranch()
    assert not w.actions


def test_ranch_verifies_specific_rewards_and_levelup():
    w = harness()
    baskets = iter([True, False])
    w.reco = lambda *args: next(baskets)
    expected = []
    def wait(nodes):
        expected.append(nodes)
        return (nodes[0], None)
    w.wait_for = wait
    w.collect_ranch()
    assert expected[0] == ['HomeRanchCollectionPage']
    assert w.actions == ['HomeRanchCollect', 'HomeCloseCollection', 'HomeLevelUp']


def test_ranch_persistent_basket_does_not_repeat_click():
    w = harness()
    w.reco = lambda *args: True
    w.wait_for = lambda nodes: (nodes[-1], None)
    with pytest.raises(RuntimeError, match='篮子仍存在'):
        w.collect_ranch()
    assert w.actions.count('HomeRanchCollect') == 1
