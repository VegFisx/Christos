#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""缺产物是不是「条件不对」造成的：把 226 条 miss 拿到多种条件下重跑。

问的问题：这些产物变不出来，是因为我们固定用煎煮(100 °C/60 min/中性)吗？
如果换成高温/强酸/强碱/无溶剂就能出来，那缺口是**条件层**的，不是模板层的。

用法：
    python -I tools\\diag_miss_conditions.py
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
    base = T.get_template("煎煮")

    # 有意的极端/不同工况：够不够极端？高温、强酸、强碱、无溶剂、低温长时
    variants = {
        "煎煮(基线)": base,
        "25°C/24h": base.with_(temperature=25.0, time_min=1440.0),
        "150°C": base.with_(temperature=150.0),
        "250°C": base.with_(temperature=250.0),
        "强酸pH1.5": base.with_(pH=1.5, catalyst="acid"),
        "强碱pH12": base.with_(pH=12.0, catalyst="base"),
        "无溶剂": base.with_(solvent="none"),
    }

    eng = SE.SmartReactEngine()
    t0 = time.time()
    recovered = {k: [] for k in variants}
    for i, m in enumerate(misses):
        want = m["want"]
        comps = [Compound(smiles=s, name="R%d" % j, herb="(bench)")
                 for j, s in enumerate(m["reactants"])]
        for name, cond in variants.items():
            try:
                prods = eng.step(comps, cond, round_no=1)
            except Exception:              # noqa: BLE001
                continue
            if any(canon(getattr(p, "smiles", "") or "") == want for p in prods):
                recovered[name].append(i)
        if (i + 1) % 50 == 0:
            print("  ...%d/%d  %.0f s" % (i + 1, len(misses), time.time() - t0))

    any_hit = set()
    for v in recovered.values():
        any_hit |= set(v)
    print("\n条件重跑 %d 条 miss，用时 %.0f s" % (len(misses), time.time() - t0))
    for name in variants:
        print("  %-12s 命中 %3d 条（%.1f%%）" % (name, len(recovered[name]),
                                              100.0 * len(recovered[name]) / max(1, len(misses))))
    print("  → 任一条件能救回：%d 条（%.1f%%）"
          % (len(any_hit), 100.0 * len(any_hit) / max(1, len(misses))))
    only_extreme = any_hit - set(recovered["煎煮(基线)"])
    print("  → 仅靠非煎煮条件才出现：%d 条" % len(only_extreme))

    out = {
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "n_miss": len(misses),
        "hit_by_variant": {k: len(v) for k, v in recovered.items()},
        "any_variant": len(any_hit),
        "only_non_default": len(only_extreme),
        "index_any": sorted(any_hit),
    }
    p = ROOT / "reports" / "miss_conditions_20261104.json"
    p.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print("写出 %s" % p)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
