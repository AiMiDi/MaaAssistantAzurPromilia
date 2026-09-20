"""Prepare offline CBT3 home indexes and selected recipe facts, without game input."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
import html
import json
from pathlib import Path
import re
import subprocess

from import_goods_wiki import BASE, ROOT, check_version, parse_product, plain

SECTIONS = {
    "products": "/home/product/", "buildings": "/home/building/",
    "tech": "/home/tech/", "orders": "/home/order/", "seeds": "/home/seed/",
    "shop": "/home/shop/", "collection": "/home/collection/",
    "items": "/items/", "guides": "/guide/",
}
OUTPUT = ROOT / "assets/resource/data/wiki"
CACHE = ROOT / ".cache"


def fetch(path, cache, offline=False):
    if not cache.exists():
        if offline:
            raise FileNotFoundError(cache)
        subprocess.run(["curl.exe", "--fail", "--silent", "--show-error", "--location",
                        "--max-time", "30", "--retry", "2", "--retry-delay", "1",
                        BASE + path, "--output", str(cache) + ".part"], check=True)
        Path(str(cache) + ".part").replace(cache)
    page = cache.read_text(encoding="utf-8")
    check_version(page)
    return page


def cards(page):
    main = re.search(r"<main\b[^>]*>(.*?)</main>", page, re.S).group(1)
    result = []
    for attrs, body in re.findall(r"<a\b([^>]*)>(.*?)</a>", main, re.S):
        fields = dict(re.findall(r'([\w-]+)="([^"]*)"', attrs))
        if "card-link" not in fields.get("class", ""):
            continue
        label = re.search(r'class="card-name"[^>]*>(.*?)</(?:span|div)>', body, re.S)
        name = fields.get("data-name") or (plain(label.group(1)) if label else None)
        if not name:
            raise ValueError("Card name missing: " + fields.get("href", ""))
        icon = re.search(r'<img[^>]*src="([^"]+)"', body)
        result.append({"name": html.unescape(name), "url": BASE + fields["href"],
                       "icon_url": BASE + icon.group(1) if icon and icon.group(1).startswith("/") else None,
                       "filters": {k[5:]: html.unescape(v) for k, v in fields.items()
                                   if k.startswith("data-") and k not in ("data-name", "data-search")}})
    if not result:
        raise ValueError("No index cards")
    return result


def table_facts(page):
    """Keep short factual table cells; prose tutorial bodies stay at the source."""
    main = re.search(r"<main\b[^>]*>(.*?)</main>", page, re.S).group(1)
    rows = []
    for row in re.findall(r"<tr\b[^>]*>(.*?)</tr>", main, re.S):
        cells = [re.sub(r"\s+", " ", plain(cell)) for cell in re.findall(r"<t[hd]\b[^>]*>(.*?)</t[hd]>", row, re.S)]
        if cells and all(len(cell) < 200 for cell in cells):
            rows.append(cells)
    return rows


def write(name, value):
    path = OUTPUT / name
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--offline", action="store_true")
    args = parser.parse_args()
    OUTPUT.mkdir(parents=True, exist_ok=True)
    CACHE.mkdir(exist_ok=True)
    indexes, pages = {}, {}
    for key, path in SECTIONS.items():
        page = fetch(path, CACHE / f"wiki_{key}.html", args.offline)
        indexes[key] = cards(page)
        pages[key] = {"url": BASE + path, "count": len(indexes[key]),
                      "sha256": hashlib.sha256(page.encode()).hexdigest()}
    selected = []
    for card in indexes["products"]:
        ident = int(card["url"].rstrip("/").split("/")[-1])
        # Goods, processing materials, equipment, capture cards, and two cheap meals.
        if (800000 <= ident < 810000 or 200000 <= ident < 210000 or
                300000 <= ident < 510000 or ident in (9100301, 9102001)):
            selected.append((ident, card))

    def recipe(entry):
        ident, card = entry
        page = fetch(f"/home/product/{ident}/", CACHE / f"recipe_{ident}.html", args.offline)
        try:
            parsed = parse_product(page, ident)
            parsed["category"] = card["filters"].get("category")
            parsed["execution_verified"] = False
            return parsed, None
        except (AttributeError, KeyError, ValueError) as exc:
            return None, {"name": card["name"], "source_url": card["url"],
                          "reason": str(exc), "table_facts": table_facts(page)}

    recipes, unresolved = [], []
    with ThreadPoolExecutor(max_workers=2) as pool:
        for count, (record, error) in enumerate(pool.map(recipe, selected), 1):
            (recipes if record else unresolved).append(record or error)
            if count % 20 == 0:
                print(f"Recipes {count}/{len(selected)}", flush=True)

    # System tables needed for scheduling and diagnosis. No automatic actions.
    detail_cards = indexes["buildings"] + indexes["seeds"] + indexes["collection"] + indexes["tech"]
    def detail(card):
        path = card["url"].removeprefix(BASE)
        cache = CACHE / ("wiki_detail_" + path.strip("/").replace("/", "_") + ".html")
        page = fetch(path, cache, args.offline)
        return {"name": card["name"], "source_url": card["url"], "table_facts": table_facts(page)}
    details = []
    with ThreadPoolExecutor(max_workers=2) as pool:
        for count, record in enumerate(pool.map(detail, detail_cards), 1):
            details.append(record)
            if count % 30 == 0:
                print(f"System pages {count}/{len(detail_cards)}", flush=True)
    write("indexes.json", indexes)
    write("recipes.json", {"recipes": recipes, "unresolved": unresolved})
    write("systems.json", details)
    manifest = {"source": BASE, "game_version": "CBT3", "wiki_data_version": "0.3.0",
                "prepared_at_utc": datetime.now(timezone.utc).isoformat(), "indexes": pages,
                "recipe_count": len(recipes), "unresolved_recipe_count": len(unresolved),
                "system_page_count": len(details),
                "files": {name: hashlib.sha256((OUTPUT / name).read_bytes()).hexdigest()
                          for name in ("indexes.json", "recipes.json", "systems.json")},
                "note": "Static preparation only. Not proof of account unlocks, live prices or UI automation support."}
    write("manifest.json", manifest)
    print(json.dumps({k: v for k, v in manifest.items() if k != "indexes"}, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
