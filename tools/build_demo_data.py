# -*- coding: utf-8 -*-
"""Build the tiny, read-only dataset shipped with Christos-Demo.

The demo contains:
  * a short excerpt of a COCONUT-derived species example (upstream CC0);
  * a small acetic-acid control example;
  * a UI-only formula preview with no real formula/database records.

It does not copy tcm.db, formula_db.json, herb_aliases_map.json, routes,
purchasable blocks, or vendor links.
"""
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

STAGE = Path(__file__).resolve().parent.parent
OUT = STAGE / "reports" / "desktop-build" / "christos-demo" / "demo_data.json"


def find_one(pattern: str) -> Path:
    hits = sorted(STAGE.glob(pattern))
    if not hits:
        raise SystemExit(f"Missing demo source: {pattern}")
    return hits[-1]


def read_products(path: Path, limit: int = 5) -> tuple[list[dict], int, int]:
    rows = []
    seen = set()
    with path.open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            if not row.get("product_inchikey") or row["product_inchikey"] in seen:
                continue
            seen.add(row["product_inchikey"])
            rows.append({
                "smiles": row.get("product_smiles", ""),
                "inchikey": row.get("product_inchikey", ""),
                "formula": row.get("formula", ""),
                "mw": row.get("mw", ""),
                "rule": row.get("rule_name", ""),
                "activation": row.get("activation", ""),
                "direction": row.get("direction_cn", ""),
                "source": row.get("source_herb", "").replace("coconut.db:", "COCONUT:"),
                "source_name": row.get("source_name", ""),
                "evidence": row.get("activation_why", ""),
            })
            if len(rows) >= limit:
                break
    with path.open(encoding="utf-8-sig", newline="") as handle:
        all_rows = list(csv.DictReader(handle))
    return rows[:limit], len(all_rows), len({r.get("product_inchikey") for r in all_rows if r.get("product_inchikey")})


def main() -> int:
    acetic = find_one(
        "reports/desktop-build/installer-test/**/20261018-113028_smiles.csv"
    )
    species = STAGE / "reports" / "demo_build" / "raw" / "20261018-113502_Glycyrrhiza uralensis.csv"
    if not species.exists():
        raise SystemExit(f"Missing demo source: {species}")

    acetic_products, acetic_rows, acetic_unique = read_products(acetic)
    species_products, species_rows, species_unique = read_products(species)
    data = {
        "product": "Christos（炼膏师）· Demo",
        "version": "0.9.0-beta-demo",
        "notice": "这是界面和流程演示，不是完整引擎；不含数据库、逆合成、可购试剂或真实方剂库。",
        "examples": [
            {
                "id": "species",
                "kind": "species",
                "title": "甘草 · 物种示例",
                "subtitle": "Glycyrrhiza uralensis · COCONUT 物种级示例（CC0 上游数据片段）",
                "inputs": ["Glycyrrhiza uralensis"],
                "condition": "水提（演示）",
                "note": "从 COCONUT 的 644 个成分中按库内原序取 3 个；下面只展示 CSV 原序去重后的前 5 条产物。不是排序、不是筛选、不是医学结论。",
                "stats": {"selected_seeds": 3, "product_rows": species_rows, "unique_products": species_unique},
                "source": "COCONUT curated dataset · 上游许可 CC0；演示只带极小片段，不分发数据库",
                "products": species_products,
            },
            {
                "id": "acetate",
                "kind": "control",
                "title": "乙酸 · 阳性对照",
                "subtitle": "简单小分子演示，不依赖 TCM 数据库",
                "inputs": ["CC(=O)O"],
                "condition": "水提（演示）",
                "note": "这是用于展示台账字段的最小对照；只展示 CSV 原序去重后的前 5 条产物。",
                "stats": {"selected_seeds": 1, "product_rows": acetic_rows, "unique_products": acetic_unique},
                "source": "用户输入的简单小分子示例；不包含用户数据库记录",
                "products": acetic_products,
            },
            {
                "id": "formula",
                "kind": "formula_preview",
                "title": "方剂工作区 · 界面预览",
                "subtitle": "同名按版本、不合并；法定剂量与份数工作流",
                "inputs": [],
                "condition": "不运行",
                "note": "正式方剂库不包含在演示包中。这里只展示版式和工作流，不提供方剂组成或预测结果。",
                "stats": {"selected_seeds": 0, "product_rows": 0, "unique_products": 0},
                "source": "界面预览；无数据库记录",
                "products": [],
            },
        ],
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"wrote {OUT} ({OUT.stat().st_size} bytes)")
    print(f"species rows={species_rows} unique={species_unique}; acetic rows={acetic_rows} unique={acetic_unique}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
