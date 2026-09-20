import sys
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from import_goods_wiki import check_version, parse_product


def page(output='<a href="/items/10/">A</a>'):
    rows = {
        "产出": output, "关联建筑": "工作台", "制作时间": "3s",
        "解锁": "默认解锁", "单次生产上限": "100",
        "可选材料": '<a href="/items/20/"><span class="dungeon-reward-name">B</span><span>×5</span></a>',
    }
    price = '<table class="table price-table"><tr><th>直接出售</th><th>订单价</th></tr><tr><td><a href="/items/103/">×11</a></td><td>—</td></tr></table>'
    table = ''.join(f'<tr><th>{k}</th><td>{v}</td></tr>' for k, v in rows.items())
    return '<main><h1>A</h1><img class="hero-icon" src="/icons/a.png">' + price + '<table>' + table + '</table></main>'


def test_price_table_does_not_swallow_recipe_and_optional_is_explicit():
    result = parse_product(page(), 123)
    assert result["item_id"] == "10"
    assert result["ingredients"] == []
    assert result["optional_ingredients"][0]["quantity"] == 5
    assert result["requires_material_choice"]
    assert result["static_prices"] == {"直接出售": {"currency_item_id": "103", "quantity": 11}}


def test_missing_output_id_is_not_guessed_from_name():
    with pytest.raises(ValueError, match="no item ID"):
        parse_product(page("A"), 123)


def test_changed_source_version_requires_review():
    check_version("数据版本 0.3.0")
    for text in ("数据版本 0.4.0", ""):
        with pytest.raises(ValueError, match="version"):
            check_version(text)
