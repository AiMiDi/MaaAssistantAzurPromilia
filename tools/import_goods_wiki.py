"""Import the reviewed CBT3 goods pages; fail if required table fields change."""
import argparse
import html
import json
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = "https://ap-cbt3.csxylic.com"
PRODUCTS = (302001, 800001, 800002, 800013, 800023, 800025, 800026,
            306001, 304001, 301002)


def check_version(page):
    match = re.search(r"数据版本\s+([\d.]+)", page)
    if not match or match.group(1) != "0.3.0":
        raise ValueError("Wiki data version changed or missing; review before importing")


def plain(value):
    return html.unescape(re.sub(r"<[^>]+>", "", value)).strip()


def parse_product(page, ident):
    main = re.search(r"<main\b[^>]*>([\s\S]*?)</main>", page).group(1)
    rows = {}
    for row in re.findall(r"<tr>(.*?)</tr>", main, re.S):
        match = re.fullmatch(r"\s*<th[^>]*>(.*?)</th>\s*<td[^>]*>(.*?)</td>\s*", row, re.S)
        if match:
            rows[plain(match.group(1))] = match.group(2)
    output_link = re.search(r'href="/items/(\d+)/"', rows["产出"])
    if not output_link:
        raise ValueError("Source output has no item ID; retain table facts for manual mapping")
    output = output_link.group(1)
    materials = {}
    for label, key in (("材料", "ingredients"), ("可选材料", "optional_ingredients")):
        materials[key] = []
        for item_id, body in re.findall(r'<a\b[^>]*href="/items/(\d+)/"[^>]*>(.*?)</a>', rows.get(label, ""), re.S):
            name = re.search(r'class="dungeon-reward-name">(.*?)</span>', body).group(1)
            quantity = int(re.search(r"×(\d+)", plain(body)).group(1))
            materials[key].append({"item_id": item_id, "name": plain(name), "quantity": quantity})
    if not any(materials.values()):
        raise ValueError(f"No ingredients for {ident}")
    icon = re.search(r'<img class="hero-icon" src="([^"]+)"', main).group(1)
    labor = re.search(r'class="tag labor-tag">工种:\s*([^<]+)', main)
    prices = {}
    price_table = re.search(r'<table class="table price-table">(.*?)</table>', main, re.S)
    if price_table:
        labels = re.findall(r"<th>(.*?)</th>", price_table.group(1), re.S)
        values = re.findall(r"<td[^>]*>(.*?)</td>", price_table.group(1), re.S)
        for label, cell in zip(labels, values):
            amount = re.search(r"×(\d+)", plain(cell))
            currency = re.search(r'href="/items/(\d+)/"', cell)
            if amount and currency:
                prices[plain(label)] = {"currency_item_id": currency.group(1), "quantity": int(amount.group(1))}
    return {
        "recipe_id": str(ident), "item_id": output,
        "name": plain(re.search(r"<h1[^>]*>(.*?)</h1>", main, re.S).group(1)),
        "station": plain(rows["关联建筑"]), **materials,
        "requires_material_choice": bool(materials["optional_ingredients"]),
        "labor": plain(labor.group(1)) if labor else None,
        "static_prices": prices,
        "base_seconds": int(plain(rows["制作时间"]).removesuffix("s")),
        "max_batch": int(plain(rows["单次生产上限"])),
        "unlock": plain(rows["解锁"]),
        "source_url": f"{BASE}/home/product/{ident}/", "icon_url": BASE + icon,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cached", action="store_true", help="Use previously fetched HTML")
    args = parser.parse_args()
    cache = ROOT / ".cache"
    cache.mkdir(exist_ok=True)
    recipes = []
    for ident in PRODUCTS:
        path = cache / f"recipe_{ident}.html"
        if not args.cached:
            subprocess.run(["curl.exe", "--fail", "--silent", "--show-error", "--location",
                            "--max-time", "25", f"{BASE}/home/product/{ident}/",
                            "--output", str(path)], check=True)
        page = path.read_text(encoding="utf-8")
        check_version(page)
        recipes.append(parse_product(page, ident))
    result = {"source": BASE, "game_version": "CBT3", "wiki_data_version": "0.3.0",
              "scope": "Current workbench goods and their reviewed intermediates",
              "recipes": recipes}
    target = ROOT / "assets/resource/data/workbench_goods.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(f"Imported {len(recipes)} recipes into {target}")


if __name__ == "__main__":
    main()
