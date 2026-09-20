import pytest
from crafting import load_catalog, plan_target


def test_chick_uses_stock_then_builds_missing_boards():
    plan = plan_target(load_catalog(), "1200001", 2,
                       {"1200001": 0, "350000": 6, "300000": 12})
    assert plan["ready"]
    assert [(s["name"], s["quantity"]) for s in plan["steps"]] == [("软木板", 4), ("苗鸡木雕", 2)]


def test_existing_target_needs_no_material_reading():
    plan = plan_target(load_catalog(), "1200001", 2, {"1200001": 2})
    assert plan["ready"] and not plan["steps"]


def test_unknown_is_not_zero_and_shortage_blocks_execution():
    assert not plan_target(load_catalog(), "1200001", 1, {})["ready"]
    plan = plan_target(load_catalog(), "1200001", 1,
                       {"1200001": 0, "350000": 0, "300000": 14})
    assert plan["shortages"] == {"300000": 1}
    assert not plan["ready"]


def test_protect_ingredient_stock():
    plan = plan_target(load_catalog(), "1200001", 1,
                       {"1200001": 0, "350000": 35, "300000": 15}, {"350000": 35})
    assert [s["quantity"] for s in plan["steps"]] == [5, 1]
    assert plan["ready"]


def test_optional_inputs_are_not_assumed_free():
    plan = plan_target(load_catalog(), "350006", 1, {"350006": 0})
    assert plan["material_choices"] == ["350006"]
    assert not plan["ready"]


def test_shared_material_is_not_double_spent_and_batches_split():
    cat = {
        "a": {"name": "a", "station": "s", "max_batch": 2, "ingredients": [{"item_id": "b", "quantity": 1}, {"item_id": "raw", "quantity": 1}]},
        "b": {"name": "b", "station": "s", "max_batch": 10, "ingredients": [{"item_id": "raw", "quantity": 1}]},
    }
    plan = plan_target(cat, "a", 3, {"a": 0, "b": 0, "raw": 5})
    assert plan["shortages"] == {"raw": 1}
    assert [s["quantity"] for s in plan["steps"]] == [3, 2, 1]
    cat["b"]["ingredients"] = [{"item_id": "a", "quantity": 1}]
    with pytest.raises(ValueError, match="循环"):
        plan_target(cat, "a", 1, {"a": 0, "b": 0})


@pytest.mark.parametrize("quantity", [-1, 0, True, 1.5])
def test_invalid_quantity(quantity):
    with pytest.raises(ValueError):
        plan_target(load_catalog(), "1200001", quantity, {})
