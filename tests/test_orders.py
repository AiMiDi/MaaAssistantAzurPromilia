import sys
from pathlib import Path

import pytest

from orders import assess_order
from types import SimpleNamespace
from order_workflow import open_board, replenish, card_read

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from import_orders_wiki import parse_order


CATALOG = [dict(order_id='1', name='软木征集', materials=[dict(item_id='300000', quantity=200)])]


def test_order_requires_matching_live_amount_and_known_stock():
    assert assess_order(CATALOG, '软木征集', {'300000': 200}, {'300000': 210})['ready']
    assert not assess_order(CATALOG, '软木征集', {'300000': 20}, {'300000': 210})['ready']
    unknown = assess_order(CATALOG, '软木征集', {'300000': 200}, {})
    assert unknown['unknown_inventory'] == ['300000']
    assert not unknown['ready']


def test_order_reserve_and_exact_title():
    result = assess_order(CATALOG, '软木征集', {'300000': 200}, {'300000': 210}, {'300000': 20})
    assert result['shortages'] == {'300000': 10}
    assert not result['ready']
    assert not assess_order(CATALOG, '软木大量征集', {'300000': 200}, {'300000': 210})['ready']


@pytest.mark.parametrize('quantity', [0, -1, True, 1.5])
def test_bad_requirement_stops(quantity):
    with pytest.raises(ValueError):
        assess_order(CATALOG, '软木征集', {'300000': quantity}, {'300000': 300})


def test_wiki_parser_preserves_item_ids_and_amounts():
    page = '''<main><h1>软木征集</h1><span>类型 10</span><span>解锁 Lv10</span>
    <table><tr><th>需求材料</th><td><a href="/items/300000/">
    <span class="dungeon-reward-name">软木</span><span>×200</span></a></td></tr></table>
    </main>数据版本 0.3.0'''
    row = parse_order(page, '1101003')
    assert row['materials'] == [{'item_id': '300000', 'name': '软木', 'quantity': 200}]
    assert row['unlock_level'] == 10
    with pytest.raises(ValueError):
        parse_order(page.replace('0.3.0', '0.4.0'), '1101003')


def test_open_board_optional_settlement_and_forecast(monkeypatch):
    pages = iter(['OrderSettlement', 'OrderNews', 'OrderMerchantPage', 'OrderBoardPage'])
    actions = []
    w = SimpleNamespace(frame=lambda: next(pages), reco=lambda name, page: name == page,
                        act=actions.append)
    monkeypatch.setattr('order_workflow.save_forecast', lambda _: actions.append('save-forecast'))
    open_board(w)
    assert actions == ['OrderSettlementConfirm', 'save-forecast', 'OrderNewsClose', 'OrderSelectBoard']


def test_open_board_unknown_scene_does_not_move():
    w = SimpleNamespace(frame=lambda: None, reco=lambda *args: False,
                        act=lambda name: pytest.fail('Unexpected input: ' + name))
    with pytest.raises(RuntimeError, match='看板旁'):
        open_board(w)


def test_replenish_calls_crafting_then_returns_to_same_board(monkeypatch):
    calls = []
    monkeypatch.setattr('workbench.run_target', lambda w, p: calls.append(p))
    w = SimpleNamespace(log=lambda _: None, act=lambda n: calls.append(n),
                        navigate=lambda n: calls.append(n), wait_for=lambda n: calls.append(n))
    assert replenish(w, [{'item_id': '1200001', 'quantity': 28, 'name': '苗鸡木雕委托'}])
    assert calls[0] == 'OrderClose'
    assert calls[1] == {'item_id': '1200001', 'quantity': 28, 'execute': True}
    assert calls[-1] == ['OrderNearby']


def test_unmakeable_order_preserved_without_crafting():
    w = SimpleNamespace(log=lambda _: None, act=lambda _: pytest.fail('Must not navigate'))
    assert not replenish(w, [{'item_id': '302019', 'quantity': 20, 'name': '兽灵之角征集'}])


def test_clipped_order_never_submitted():
    assert card_read(None, None, SimpleNamespace(box=[470,570,110,20]), []) is None
