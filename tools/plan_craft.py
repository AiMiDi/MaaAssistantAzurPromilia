"""Preview a target-stock plan using supplied inventory; never connects to the game."""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "agent"))
from crafting import load_catalog, plan_target


def quantities(entries):
    result = {}
    for entry in entries:
        key, value = entry.split("=", 1)
        if key in result:
            raise ValueError("重复的物品库存：" + key)
        result[key] = int(value)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", required=True, help="Item ID or unique name in reviewed catalogue")
    parser.add_argument("--quantity", required=True, type=int, help="Desired final stock")
    parser.add_argument("--stock", action="append", default=[], metavar="ITEM_ID=COUNT")
    parser.add_argument("--reserve", action="append", default=[], metavar="ITEM_ID=COUNT")
    args = parser.parse_args()
    catalog = load_catalog()
    target = args.target
    if target not in catalog:
        matches = [key for key, value in catalog.items() if value["name"] == target]
        if len(matches) != 1:
            parser.error("目标名称不存在或不唯一，请使用物品 ID")
        target = matches[0]
    try:
        plan = plan_target(catalog, target, args.quantity, quantities(args.stock), quantities(args.reserve))
    except ValueError as exc:
        parser.error(str(exc))
    print(json.dumps(plan, ensure_ascii=False, indent=2))
    return 0 if plan["ready"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
