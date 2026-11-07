#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""① 缺产物是不是「我们自己筛掉的」：把引擎丢弃记录打开，看 target 在不在里面。

引擎里会让产物消失的地方有四类：
  gate     条件门控（activation<=0，这条反应在该条件下判为不发生）
  extent   反应进程门（默认关）
  cap      每对产物上限（max_products_per_pair）
  dedup    结构去重（同一结构已被别的规则产出，只补记 also_rules）
  classify classify_product 判 keep=False（过滤小分子/无意义结构）

用法：
    python -I tools\\diag_miss_filters.py
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

ROOT = Path(__file__).resolve().parent.parent
for _p in (ROOT / "core", ROOT / "tools", ROOT / "conditions", ROOT / "libs"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from rdkit import Chem, RDLogger  # noqa: E402

RDLogger.DisableLog("rdApp.*")

MISS = ROOT / "reports" / "miss_diag.jsonl"


def canon(s: str) -> str:
    m = Chem.MolFromSmiles(s) if s else None
    return Chem.MolToSmiles(m) if m is not None else ""


def main() -> int:
    import smartreact_engine as SE
    import templates as T
    from engine import Compound

    misses = [json.loads(l) for l in MISS.open(encoding="utf-8")]
    cond = T.get_template("煎煮")
    t0 = time.time()

    # 两种引擎配置：默认 / 上限放大（看是不是被 cap 截断）
    engs = {
        "default": (SE.SmartReactEngine(), None),
        "uncapped": (SE.SmartReactEngine(max_products_per_pair=4096,
                                         max_pairs=100000), "uncapped"),
    }
    found_by = {k: [] for k in ("gate", "extent", "cap", "dedup", "classify", "kept")}
    detail = []
    for i, m in enumerate(misses):
        want = m["want"]
        comps = [Compound(smiles=s, name="R%d" % j, herb="(bench)")
                 for j, s in enumerate(m["reactants"])]
        for name, (eng, _tag) in engs.items():
            eng.debug_drops = []
            try:
                prods = eng.step(comps, cond, round_no=1)
            except Exception:                 # noqa: BLE001
                continue
            kept = {canon(getattr(p, "smiles", "") or "") for p in prods}
            if want in kept:
                found_by["kept"].append(i)
                detail.append({"i": i, "eng": name, "where": "kept"})
                continue
            hit = None
            rules = []
            for d in eng.debug_drops:
                if d.get("smiles") and canon(d["smiles"]) == want:
                    hit = hit or d["reason"]
                    rules.append(d["rule"])
            if hit:
                found_by[hit].append(i)
                detail.append({"i": i, "eng": name, "where": hit, "rules": rules[:5]})
        if (i + 1) % 50 == 0:
            print("  ...%d/%d  %.0f s" % (i + 1, len(misses), time.time() - t0))

    n = max(1, len(misses))
    print("\n226 条 miss 诊断（%.0f s）：" % (time.time() - t0))
    for k in ("kept", "gate", "extent", "cap", "dedup", "classify"):
        print("  %-9s %3d 条（%.1f%%）" % (k, len(found_by[k]), 100.0 * len(found_by[k]) / n))
    rescued = sum(len(v) for k, v in found_by.items() if k != "kept")
    print("  → 被我们筛掉/截断、其实变出来了：%d 条（%.1f%%）"
          % (rescued, 100.0 * rescued / n))

    out = {
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "n_miss": len(misses),
        "found": {k: len(v) for k, v in found_by.items()},
        "rescued_total": rescued,
        "detail": detail[:400],
    }
    p = ROOT / "reports" / "miss_filters_20261104.json"
    p.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print("写出 %s" % p)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
