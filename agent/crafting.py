"""Inventory-aware planning from the reviewed CBT3 recipe catalogue."""
import json
from pathlib import Path


def load_catalog():
    root = Path(__file__).resolve().parents[1]
    path = root / "resource/data/workbench_goods.json"
    if not path.exists():
        path = root / "assets/resource/data/workbench_goods.json"
    return {r["item_id"]: r for r in json.loads(path.read_text(encoding="utf-8"))["recipes"]}


def plan_target(catalog, target, quantity, inventory, reserves=None):
    """Reach a total target stock. Missing inventory keys are unknown, never zero.

    Reserves protect ingredient stock; target quantity itself is the desired total.
    Only fixed-input recipes can be expanded. Plans with shortages or unknowns
    are previews and must not be executed.
    """
    reserves = reserves or {}
    for value in [quantity, *inventory.values(), *reserves.values()]:
        if type(value) is not int or value < 0:
            raise ValueError("数量必须为非负整数")
    if quantity == 0 or target not in catalog:
        raise ValueError("目标配方不存在或目标数量为零")
    available = {k: max(0, v - reserves.get(k, 0)) for k, v in inventory.items()}
    available[target] = inventory.get(target, 0)
    steps, shortages, unknown, choices = [], {}, set(), set()

    def consume(item, amount, chain):
        if item not in inventory:
            unknown.add(item)
            return
        used = min(available.get(item, 0), amount)
        available[item] = available.get(item, 0) - used
        missing = amount - used
        if not missing:
            return
        if item in chain:
            raise ValueError("配方出现循环依赖：" + item)
        recipe = catalog.get(item)
        if recipe is None:
            shortages[item] = shortages.get(item, 0) + missing
            return
        if recipe.get("requires_material_choice"):
            choices.add(item)
            return
        for material in recipe["ingredients"]:
            consume(material["item_id"], missing * material["quantity"], chain + (item,))
        limit = recipe["max_batch"]
        if type(limit) is not int or limit < 1:
            raise ValueError("无效的生产批次上限")
        while missing:
            batch = min(missing, limit)
            steps.append({"item_id": item, "name": recipe["name"],
                          "station": recipe["station"], "quantity": batch})
            missing -= batch

    consume(target, quantity, ())
    return {"target": target, "quantity": quantity, "steps": steps,
            "shortages": shortages, "unknown_inventory": sorted(unknown),
            "material_choices": sorted(choices),
            "ready": not (shortages or unknown or choices)}
