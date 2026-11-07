# -*- coding: utf-8 -*-
"""Merge the three bounded prediction shards for Christos-Demo."""
from __future__ import annotations

import json
import sys
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

STAGE = Path(__file__).resolve().parent.parent
BASE = STAGE / "reports" / "desktop-build" / "christos-demo"
OUT = BASE / "demo_predictions.json"


def main() -> int:
    parts = []
    for name in ("p1", "p2", "p3"):
        path = BASE / f"demo_predictions_{name}.json"
        if not path.exists():
            raise SystemExit(f"missing shard: {path}")
        parts.append(json.loads(path.read_text(encoding="utf-8")))
    items, failures = {}, []
    for part in parts:
        items.update(part.get("items") or {})
        failures.extend(part.get("failures") or [])
    OUT.write_text(json.dumps({
        "notice": "Precomputed bounded demo samples; no database distribution.",
        "items": items,
        "failures": failures,
    }, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"merged shards={len(parts)} items={len(items)} failures={len(failures)} -> {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
