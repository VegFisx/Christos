#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""漏检补充分析：92% 的命中里，有多少依赖「见过很多次」的通用模板，多少依赖「只见过一两次」的模板。

背景（B 的第一部分结论）：`templates.txt` 的 9,770 条出处反应与测试集的 50,016 条
**没有任何一条完全相同**（严格反应 0/50,016，底物集合相同 0/50,016）。
但引擎真正的候选还来自 `reports/mined_forward_templates_full_s5.jsonl`（41,619 条，挖自 ORD，
带 `support` 字段），那批模板没有逐条出处反应，只能从**支持度**侧面判断：

  * support 很大的模板 = 通用反应规则（例如硝基还原 23,829 次）；
  * support 1~2 的模板 = 可能只对应极少数具体反应，接近「记忆」。

做法：抽 N 条测试反应单轮跑（煎煮、立体开），对每条「命中真产物」的台账行取
`template_smarts`（第 91 轮新加的列），再按来源分类并查 support。

用法：
    python -I tools\\analyze_leakage_support.py [--n 300]
输出：reports/leakage_support_20261104.json
"""
from __future__ import annotations

import argparse
import ast
import json
import random
import sys
import time
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

ROOT = Path(__file__).resolve().parent.parent
# 注意顺序：conditions 必须在 libs/smartreact 之前，否则 `import templates` 会命中
# libs/smartreact/templates.py（那是模板类实现，不是条件模板），报相对导入错误。
for _p in (ROOT / "core", ROOT / "tools", ROOT / "conditions", ROOT / "libs"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import query_base as qb   # noqa: E402
import reaction_paths as rp  # noqa: E402

from rdkit import Chem, RDLogger  # noqa: E402

RDLogger.DisableLog("rdApp.*")

MINED = ROOT / "reports" / "mined_forward_templates_full_s5.jsonl"
BASE = ROOT / "libs" / "smartreact" / "data" / "templates.txt"
TESTSET = ROOT / "reports" / "paper" / "data" / "uspto50k_canon.jsonl"
OUT = ROOT / "reports" / "leakage_support_20261104.json"


def canon(s: str) -> str:
    m = Chem.MolFromSmiles(s) if s else None
    return Chem.MolToSmiles(m) if m is not None else ""


def load_support():
    sup = {}
    with MINED.open(encoding="utf-8") as f:
        for line in f:
            d = json.loads(line)
            t = d.get("template") or ""
            if t:
                sup[t] = int(d.get("support") or 0)
    base = set()
    with BASE.open(encoding="utf-8") as f:
        f.readline()
        for line in f:
            p = line.rstrip("\n").split("\t")
            if len(p) >= 5 and p[3]:
                base.add(p[3])
    return sup, base


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=300)
    ap.add_argument("--seed", type=int, default=20261104)
    a = ap.parse_args()

    sup, base = load_support()
    print("mined 模板 %d 条（support 中位 %d）；base 模板 %d 条"
          % (len(sup), sorted(sup.values())[len(sup) // 2] if sup else 0, len(base)))

    rows = []
    with TESTSET.open(encoding="utf-8") as f:
        for line in f:
            rows.append(json.loads(line))
    random.Random(a.seed).shuffle(rows)
    picked = rows[:a.n]

    # 引擎只建一次（与 bench 同一档默认配置），否则每条反应重建要 ~2 秒。
    import smartreact_engine as SE
    import templates as T
    from engine import Compound

    eng = SE.SmartReactEngine()
    cond = T.get_template("煎煮")

    stats = {"hits": 0, "by_source": {}, "supports": [], "n": 0, "no_template_smarts": 0,
             "errors": 0, "first_error": ""}
    t0 = time.time()
    for d in picked:
        rl = d["reactants"]
        rl = ast.literal_eval(rl) if isinstance(rl, str) else rl
        comps = []
        bad = False
        for i, smi in enumerate(rl[:2]):
            if Chem.MolFromSmiles(smi) is None:
                bad = True
                break
            comps.append(Compound(smiles=smi, name="R%d" % i, herb="(bench)"))
        if bad or not comps:
            continue
        want = canon(d.get("product") or "")
        if not want:
            continue
        try:
            prods = eng.step(comps, cond, round_no=1)
        except Exception as ex:
            stats["errors"] += 1
            if not stats["first_error"]:
                stats["first_error"] = "%s: %s" % (type(ex).__name__, ex)
            continue
        stats["n"] += 1
        hit = next((p for p in prods if canon(getattr(p, "smiles", "") or "") == want), None)
        if hit is None:
            continue
        stats["hits"] += 1
        tm = getattr(hit, "template_smarts", "") or ""
        if not tm:
            stats["no_template_smarts"] += 1
            src = "no_smarts"
        elif tm in base:
            src = "base_templates.txt"
        elif tm in sup:
            src = "mined_ord"
            stats["supports"].append(sup[tm])
        else:
            src = "curated_or_other"
        stats["by_source"][src] = stats["by_source"].get(src, 0) + 1

    s = sorted(stats["supports"])
    out = {
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "n_sampled": stats["n"],
        "n_hits": stats["hits"],
        "hit_share": round(stats["hits"] / max(1, stats["n"]), 4),
        "by_source": stats["by_source"],
        "mined_support": {
            "n": len(s),
            "median": s[len(s) // 2] if s else None,
            "p10": s[int(len(s) * 0.1)] if s else None,
            "share_le2": round(sum(1 for x in s if x <= 2) / max(1, len(s)), 4),
            "share_le10": round(sum(1 for x in s if x <= 10) / max(1, len(s)), 4),
            "share_ge100": round(sum(1 for x in s if x >= 100) / max(1, len(s)), 4),
        },
        "no_template_smarts": stats["no_template_smarts"],
        "seconds": round(time.time() - t0, 1),
    }
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
