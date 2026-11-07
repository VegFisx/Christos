# -*- coding: utf-8 -*-
r"""诊断：负例假阳性 90% 是**从哪条路径来的**？

## 为什么做这个
`tools/measure_hte_validation.py` 给出的数字是"不该反应的组里，90% 也说能"。
但"假阳性"只是一个总账，不清楚是哪一类原因：
  ① 目标产物由**多种模板/多条路径**生成（删一条没用）
  ② 生成它的模板**支持数很低**（ORD 里只见过 1~2 次，属噪声模板）
  ③ 生成它的模板**不在 37 类里**（自抽模板，绕过条件门控 -> activation=1.0）
  ④ 生成它的模板**在 37 类里**，但条件门控放行了（温度/溶剂窗口没起作用）
  ⑤ 目标产物是**混合物/盐**等拆分后碰巧命中

## 口径（先定死）
* 输入：`reports/hte_validation_result.json` 的 `rows.neg`（负例逐对结果）
* 对每个负例组，重跑该对的引擎枚举，取**产出目标产物的那些结果**，记录：
  - `rule_name`（37 类名或 mined_extra / mined_mono）
  - 该规则的 `activation`（条件门控给的权重）
  - 模板支持数（能取到就记，取不到记 None）
  - 同一产物被**几条不同规则**生成
* 汇总：按规则、按是否 37 类、按支持数分档、按产物重原子数分档
* 输出：`reports/diagnose_false_positive.json` + 控制台摘要

用法:
    & $py -u tools\diagnose_false_positive.py
"""
from __future__ import annotations

import json
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

STAGE = Path(r"D:\ProgramData\DSHNS\chemreact-staging")
for _p in (STAGE / "libs", STAGE / "core", STAGE / "conditions", STAGE / "rules",
           STAGE / "tools", STAGE / "sources"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

RESULT = STAGE / "reports" / "hte_validation_result.json"
OUT = STAGE / "reports" / "diagnose_false_positive.json"

CLASS37 = None       # 运行时填：37 类名集合


def main() -> int:
    global CLASS37
    if not RESULT.exists():
        print(f"缺 {RESULT}：先跑 tools\\measure_hte_validation.py")
        return 2
    data = json.loads(RESULT.read_text(encoding="utf-8"))
    neg = data["rows"]["neg"]
    pos = data["rows"]["pos"]
    print(f"负例 {len(neg)} 组（其中假阳性 {sum(1 for r in neg if r['reproduced'])} 组）")
    print(f"正例 {len(pos)} 组（其中命中 {sum(1 for r in pos if r['reproduced'])} 组）")

    from engine import Compound
    from smartreact_engine import SmartReactEngine, _load_reaction_names
    import templates as T

    CLASS37 = set(_load_reaction_names().keys())
    # 模板支持数：自抽模板文件里带 support 字段
    support = {}
    for fn, key in (("mined_forward_templates.jsonl", "mined_extra"),
                    ("mined_mono_templates.jsonl", "mined_mono")):
        p = STAGE / "reports" / fn
        if not p.exists():
            continue
        sup = []
        with open(p, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    sup.append(int(json.loads(line).get("support") or 0))
        if sup:
            sup.sort()
            support[key] = {"n": len(sup), "min": sup[0], "median": sup[len(sup) // 2],
                            "max": sup[-1]}

    eng = SmartReactEngine()
    base = T.get_template("煎煮")
    cond = type(base)(solvent="dmso", temperature=100.0, time_min=60.0, pH=7.0,
                      catalyst="metal", atmosphere="air")

    rows = []
    t0 = time.time()
    for i, r in enumerate(neg):
        if not r.get("reproduced"):
            continue
        comps = [Compound(smiles=r["aryl"], name="A", herb="HTE"),
                 Compound(smiles=r["amine"], name="B", herb="HTE")]
        prods = eng.step(comps, cond, round_no=1)
        hits = [p for p in prods if p.smiles == r["target"]]
        rules = sorted({(p.rule_name, round(float(p.activation), 3)) for p in hits})
        rows.append({
            "aryl": r["aryl"], "amine": r["amine"], "target": r["target"],
            "source": r["source"], "solvent": r["solvent"],
            "n_total_products": len(prods),
            "n_rules_for_target": len({x[0] for x in rules}),
            "rules": [{"rule": a, "activation": b} for a, b in rules],
            "target_heavy_atoms": hits[0].heavy_atoms if hits else None,
        })
    print(f"重跑假阳性对完成（{time.time()-t0:.1f}s）")

    by_rule = Counter()
    by_is37 = Counter()
    n_rules_per_target = Counter()
    act_of_selfmined = Counter()
    for r in rows:
        rules = {x["rule"] for x in r["rules"]}
        for x in r["rules"]:
            by_rule[x["rule"]] += 1
            if x["rule"] in CLASS37:
                by_is37["37类（走条件门控）"] += 1
            else:
                by_is37["自抽模板（绕过门控）"] += 1
                act_of_selfmined[x["activation"]] += 1
        n_rules_per_target[min(len(rules), 5)] += 1

    summary = {
        "what": "负例假阳性（引擎在不该反应的底物对上仍声称能反应）的成因拆解",
        "n_neg": len(neg), "n_fp": len(rows),
        "by_rule": dict(by_rule.most_common()),
        "by_class37": dict(by_is37),
        "n_rules_for_target": {str(k): v for k, v in sorted(n_rules_per_target.items())},
        "selfmined_activation": {str(k): v for k, v in sorted(act_of_selfmined.items())},
        "selfmined_support": support,
        "rows": rows,
        "seconds": round(time.time() - t0, 1),
    }
    OUT.write_text(json.dumps(summary, ensure_ascii=False, indent=1), encoding="utf-8")

    print()
    print("=" * 92)
    print(f"假阳性成因（{len(rows)} 组）")
    print("=" * 92)
    print(f"  生成目标产物的规则（按出现次数）：")
    for k, v in by_rule.most_common(12):
        tag = "37类" if k in CLASS37 else "自抽"
        print(f"    {k:<32} {v:>4}  [{tag}]")
    print(f"\n  按是否 37 类（走条件门控 / 绕过门控）：{dict(by_is37)}")
    print(f"  一个目标产物由几条规则生成: {dict(sorted(n_rules_per_target.items()))}")
    print(f"  自抽模板的 activation 取值: {dict(act_of_selfmined)}")
    if support:
        print(f"  自抽模板支持数分布: {support}")
    print(f"\n-> {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
