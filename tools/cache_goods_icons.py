"""Cache the 22 researched goods icons with source and integrity metadata."""
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
import subprocess

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]


def main():
    data = ROOT / "assets/resource/data/wiki"
    folder = ROOT / "assets/resource/image/wiki_goods"
    folder.mkdir(parents=True, exist_ok=True)
    recipes = json.loads((data / "recipes.json").read_text(encoding="utf-8"))["recipes"]
    selected = [r for r in recipes if 800000 <= int(r["recipe_id"]) < 810000]

    def cache(recipe):
        path = folder / (recipe["item_id"] + ".png")
        if not path.exists():
            pending = path.with_suffix(".part")
            subprocess.run(["curl.exe", "--fail", "--silent", "--show-error", "--location",
                            "--max-time", "30", "--retry", "2", recipe["icon_url"],
                            "--output", str(pending)], check=True)
            with Image.open(pending) as img:
                if img.format != "PNG":
                    raise ValueError("Expected PNG: " + recipe["icon_url"])
                img.verify()
            pending.replace(path)
        with Image.open(path) as img:
            width, height = img.size
            img.verify()
        return {"item_id": recipe["item_id"], "name": recipe["name"],
                "source_url": recipe["icon_url"], "recipe_url": recipe["source_url"],
                "path": path.relative_to(ROOT / "assets/resource").as_posix(),
                "width": width, "height": height,
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                "recognition_verified": False}

    with ThreadPoolExecutor(max_workers=2) as pool:
        records = list(pool.map(cache, selected))
    (data / "goods_icons.json").write_text(json.dumps(records, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Validated {len(records)} source icons")


if __name__ == "__main__":
    main()
