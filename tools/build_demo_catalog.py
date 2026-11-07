# -*- coding: utf-8 -*-
"""Select a small catalog for Christos-Demo from the project data.

This is a catalog builder only. It does not copy a database into the demo:
the demo ships names/composition metadata and a few precomputed result rows.
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

STAGE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(STAGE / "sources"))
from formula import clean_token, split_ingredients

FORMULA_DB = Path(r"D:\TCMAI\data\formula_db.json")
HERB_SPECIES = STAGE / "data" / "herb_species.json"
OUT = STAGE / "reports" / "desktop-build" / "christos-demo" / "demo_catalog.json"
BLOCK_TOKENS = (
    "麻黄", "麻黄根", "罂粟壳", "马钱子", "洋金花", "朱砂", "雄黄", "蟾酥",
    "川乌", "草乌", "附子", "细辛",
)


def main() -> int:
    species = json.loads(HERB_SPECIES.read_text(encoding="utf-8"))
    formulas = json.loads(FORMULA_DB.read_text(encoding="utf-8"))
    counts = Counter()
    for records in formulas.values():
        for rec in records:
            for token in split_ingredients(rec.get("peifang") or ""):
                name = clean_token(token)
                if name in species:
                    counts[name] += 1

    herbs = []
    for name, n in counts.most_common():
        if any(x in name for x in BLOCK_TOKENS):
            continue
        info = species.get(name) or {}
        species_list = info.get("species") or []
        latin_list = info.get("latin_raw") or []
        if not species_list:
            continue
        herbs.append({
            "name": name,
            "species": str(species_list[0]),
            "latin": str(latin_list[0]) if latin_list else "",
            "formula_hits": n,
        })
        if len(herbs) >= 100:
            break
    herb_names = {h["name"] for h in herbs}

    picked = []
    seen_names = set()
    for name, records in sorted(formulas.items(), key=lambda kv: (-len(kv[1]), kv[0])):
        if name in seen_names:
            continue
        for rec in records:
            raw = str(rec.get("peifang") or "")
            if any(x in raw for x in BLOCK_TOKENS):
                continue
            ingredients = [clean_token(t) for t in split_ingredients(raw)]
            ingredients = [x for x in ingredients if x]
            if not (4 <= len(ingredients) <= 6):
                continue
            matches = [x for x in ingredients if x in herb_names]
            if len(matches) < 3:
                continue
            picked.append({
                "name": name,
                "ingredients": ingredients,
                "mapped_ingredients": matches,
                "source": str(rec.get("chuchu") or ""),
                "category": str(rec.get("category") or ""),
            })
            seen_names.add(name)
            break
        if len(picked) >= 50:
            break

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({
        "notice": "Demo catalog derived from the local project data; not a database distribution.",
        "herbs": herbs,
        "formulas": picked,
    }, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"catalog={OUT} herbs={len(herbs)} formulas={len(picked)}")
    print("top herbs:", ", ".join(h["name"] for h in herbs[:15]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
