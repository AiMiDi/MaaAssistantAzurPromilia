from types import SimpleNamespace

import pytest

from workflows import Workflow


def feeder(counts, cookie=True):
    w = Workflow(SimpleNamespace(tasker=SimpleNamespace(stopping=False)))
    w.actions = []
    w.act = w.actions.append
    w.navigate = lambda _: None
    w.wait_for = lambda _: None
    w.frame = lambda: None
    w.reco = lambda node, _: cookie if node == 'HomeFoodCookie' else True
    values = iter(counts)
    w.counter = lambda node: next(values)
    w.log = lambda _: None
    return w


def test_cookie_feed_verifies_satiety_increase():
    w = feeder([(525,1800), (1800,1800)])
    w.feed()
    assert 'HomeFoodSelectCookie' in w.actions
    assert 'HomeFoodAddAll' not in w.actions


@pytest.mark.parametrize('full,cookie', [(True, True), (False, False)])
def test_full_or_no_cookie_keeps_other_food(full, cookie):
    w = feeder([(1800 if full else 525,1800)], cookie=cookie)
    w.feed()
    assert 'HomeFoodSelectCookie' not in w.actions
    assert 'HomeFoodAddAll' not in w.actions


def test_click_without_satiety_increase_is_not_success():
    w = feeder([(525,1800), (525,1800)])
    with pytest.raises(RuntimeError, match='未确认'):
        w.feed()


def test_full_table_skips_new_production():
    w = feeder([(1800,1800)])
    assert not w.food_needs_cooking()
