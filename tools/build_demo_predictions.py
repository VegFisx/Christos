# -*- coding: utf-8 -*-
"""Precompute a bounded prediction sample for every Christos-Demo catalog entry.

Each entry is capped at one component, one round and five unique product rows.
No database is copied into the demo package.
"""
from __future__ import annotations

import csv
import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

STAGE = Path(__file__).resolve().parent.parent
CATALOG = STAGE / "reports" / "desktop-build" / "christos-demo" / "demo_catalog.json"
DEFAULT_OUT = STAGE / "reports" / "desktop-build" / "christos-demo" / "demo_predictions.json"
DEFAULT_RAW = STAGE / "reports" / "demo_build" / "catalog_raw_v2"
PY = Path(r"D:\TCMAI\venv\Scripts\python.exe")
BRIDGE = STAGE / "integration" / "tcmai_bridge" / "chemreact.py"


def products_from_csv(path: Path, limit: int = 5):
    rows, seen = [], set()
    with path.open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            ik = row.get("product_inchikey", "")
            if not ik or ik in seen:
                continue
            seen.add(ik)
            rows.append({
                "smiles": row.get("product_smiles", ""),
                "inchikey": ik,
                "formula": row.get("formula", ""),
                "mw": row.get("mw", ""),
                "rule": row.get("rule_name", ""),
                "activation": row.get("activation", ""),
                "direction": row.get("direction_cn", ""),
                "source": row.get("source_herb", "").replace("coconut.db:", "COCONUT:"),
                "evidence": row.get("activation_why", ""),
            })
            if len(rows) >= limit:
                break
    with path.open(encoding="utf-8-sig", newline="") as handle:
        all_rows = list(csv.DictReader(handle))
    return rows, len(all_rows), len({r.get("product_inchikey") for r in all_rows if r.get("product_inchikey")})


def run_one(label: str, herb: str, index: int, total: int, raw: Path, sample_basis: str = ""):
    out = raw / f"{index:03d}"
    out.mkdir(parents=True, exist_ok=True)
    cmd = [str(PY), "-u", str(BRIDGE), "predict", "--herb", herb,
           "--limit", "1", "--rounds", "1", "--cond", "水提",
           "--max-pairs", "20", "--out", str(out), "--no-report", "--lang", "zh"]
    proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                          errors="replace", timeout=90)
    csvs = sorted(out.glob("*.csv"), key=lambda p: p.stat().st_mtime)
    if proc.returncode != 0 or not csvs:
        return {"label": label, "herb": herb, "error": (proc.stderr or proc.stdout or "")[-500:]}
    products, all_rows, unique = products_from_csv(csvs[-1])
    return {"label": label, "herb": herb, "sample_basis": sample_basis, "products": products,
            "stats": {"product_rows": all_rows, "unique_products": unique}}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--start", type=int, default=0)
    parser.add_argument("--end", type=int, default=0)
    parser.add_argument("--out", default=str(DEFAULT_OUT))
    parser.add_argument("--raw", default=str(DEFAULT_RAW))
    args = parser.parse_args()
    catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
    out = Path(args.out)
    raw = Path(args.raw)
    raw.mkdir(parents=True, exist_ok=True)
    items = [("herb", h) for h in catalog["herbs"]] + [
        ("formula", f) for f in catalog["formulas"]
    ]
    if args.start or args.end:
        items = items[max(0, args.start - 1):args.end or None]
    results, failures = {}, []
    started = time.time()
    for i, (kind, item) in enumerate(items, 1):
        if kind == "herb":
            label = f'{item["name"]} · {item["species"]}'
            target = item["species"]
            sample_basis = ""
        else:
            label = item["name"]
            # Keep the preview bounded: use the first two mapped ingredients.
            target = ",".join(item.get("mapped_ingredients", [])[:2])
            sample_basis = "预计算预览仅取前两味：" + target
        try:
            result = run_one(label, target, i, len(items), raw, sample_basis)
        except Exception as exc:  # noqa: BLE001 - count every failed item
            result = {"label": label, "herb": target, "error": f"{type(exc).__name__}: {exc}"}
        if "error" in result:
            failures.append(result)
            print(f"[{i}/{len(items)}] FAIL {label}: {result['error'][:120]}")
        else:
            results[f"{kind}:{item['name']}"] = result
            print(f"[{i}/{len(items)}] {label}: {len(result['products'])} rows")
    out.write_text(json.dumps({
        "notice": "Precomputed bounded demo samples; no database distribution.",
        "items": results,
        "failures": failures,
    }, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"wrote {out} results={len(results)} failures={len(failures)} seconds={time.time()-started:.1f}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
