"""Order validation: live quantities must agree with a Wiki variant before input."""
import json
from pathlib import Path


def load_orders():
    root = Path(__file__).resolve().parents[1]
    path = root / 'resource/data/wiki/orders.json'
    if not path.exists():
        path = root / 'assets/resource/data/wiki/orders.json'
    return json.loads(path.read_text(encoding='utf-8'))['orders']


def assess_order(catalog, name, requirements, inventory, reserves=None):
    """Exact name + item IDs + amounts disambiguate level-dependent Wiki variants.

    Inputs are keyed by item ID. An absent stock count is unknown, not zero.
    This decision never authorizes selling an entire inventory or refreshing orders.
    """
    reserves = reserves or {}
    for values in (requirements, inventory, reserves):
        if any(type(v) is not int or v < 0 for v in values.values()):
            raise ValueError('订单数量必须为非负整数')
    if not requirements or any(v == 0 for v in requirements.values()):
        raise ValueError('订单需求不能为空或为零')
    matches = [row for row in catalog if row['name'] == name and
               {m['item_id']: m['quantity'] for m in row['materials']} == requirements]
    unknown = sorted(set(requirements) - set(inventory))
    shortages = {item: amount + reserves.get(item, 0) - inventory[item]
                 for item, amount in requirements.items()
                 if item in inventory and inventory[item] < amount + reserves.get(item, 0)}
    return {'ready': bool(matches) and not unknown and not shortages,
            'matched_order_ids': [row['order_id'] for row in matches],
            'wiki_match': bool(matches), 'unknown_inventory': unknown,
            'shortages': shortages}
