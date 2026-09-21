"""Import factual order requirements from the user-selected CBT3 Wiki."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
import re

from import_goods_wiki import BASE, ROOT, check_version, plain
from prepare_home_reference import fetch


def parse_order(page, ident):
    check_version(page)
    main = re.search(r'<main\b[^>]*>(.*?)</main>', page, re.S).group(1)
    name = plain(re.search(r'<h1[^>]*>(.*?)</h1>', main, re.S).group(1))
    row = re.search(r'<th[^>]*>需求材料</th>\s*<td[^>]*>(.*?)</td>', main, re.S)
    if not row:
        raise ValueError(f'Missing materials: {ident}')
    materials = []
    for item_id, body in re.findall(r'<a\b[^>]*href="/items/(\d+)/"[^>]*>(.*?)</a>', row.group(1), re.S):
        label = re.search(r'class="dungeon-reward-name">(.*?)</span>', body, re.S)
        quantity = re.search(r'×\s*(\d+)', plain(body))
        if not label or not quantity or int(quantity.group(1)) <= 0:
            raise ValueError(f'Invalid requirement: {ident}')
        materials.append({'item_id': item_id, 'name': plain(label.group(1)), 'quantity': int(quantity.group(1))})
    if not materials:
        raise ValueError(f'No item IDs: {ident}')
    level = re.search(r'解锁\s*Lv(\d+)', plain(main))
    kind = re.search(r'类型\s+(\d+)', plain(main))
    return {'order_id': str(ident), 'name': name, 'type': int(kind.group(1)) if kind else None,
            'unlock_level': int(level.group(1)) if level else None, 'materials': materials,
            'source_url': f'{BASE}/home/order/{ident}/',
            'source_sha256': hashlib.sha256(page.encode()).hexdigest()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--offline', action='store_true')
    args = parser.parse_args()
    index = json.loads((ROOT / 'assets/resource/data/wiki/indexes.json').read_text(encoding='utf-8'))['orders']
    cache = ROOT / '.cache/orders'
    cache.mkdir(parents=True, exist_ok=True)
    def one(card):
        ident = card['url'].rstrip('/').split('/')[-1]
        return parse_order(fetch(f'/home/order/{ident}/', cache / f'{ident}.html', args.offline), ident)
    rows = []
    with ThreadPoolExecutor(max_workers=2) as pool:
        for row in pool.map(one, index):
            rows.append(row)
            if len(rows) % 50 == 0:
                print(f'{len(rows)}/{len(index)}', flush=True)
    output = ROOT / 'assets/resource/data/wiki/orders.json'
    output.write_text(json.dumps({'data_version': '0.3.0', 'source_url': BASE + '/home/order/',
                                 'orders': rows}, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')
    print(f'Imported {len(rows)} orders', flush=True)


if __name__ == '__main__':
    main()
