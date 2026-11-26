# -*- coding: utf-8 -*-
"""合并多个正向模板池（按 SMARTS 去重，support 取最大）。

用法：
  python -I tools\\merge_template_pools.py --out reports\\merged.jsonl a.jsonl b.jsonl
"""
from __future__ import annotations

import argparse
import json
import sys

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("inputs", nargs="+")
    a = ap.parse_args()
    merged = {}
    for p in a.inputs:
        n = 0
        with open(p, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                d = json.loads(line)
                t = d.get("template") or ""
                if ">>" not in t:
                    continue
                s = int(d.get("support") or 0)
                if t not in merged or s > merged[t][0]:
                    merged[t] = (s, d.get("src") or "")
                n += 1
        print("%s: %d 行" % (p, n))
    with open(a.out, "w", encoding="utf-8") as f:
        for t, (s, src) in sorted(merged.items(), key=lambda kv: -kv[1][0]):
            f.write(json.dumps({"template": t, "support": s,
                                "src": (src or "merged")}, ensure_ascii=False) + "\n")
    print("合并去重后 %d 条 -> %s" % (len(merged), a.out))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
