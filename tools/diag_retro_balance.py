# -*- coding: utf-8 -*-
r"""诊断②b：反转模板给出的切断【配平吗】？

动机：CCNC(C)=O 的一条"路线"是 CC([NH-])=O + CCO。
      数一下原子就知道对不上：C4H9NO vs C2H4NO- + C2H6O = C4H10NO-。
      -> 反转模板丢掉了小分子（水/HCl/胺…），因为它只含【带映射的原子】。

本脚本量化：
  ① 所有切断方案里，质量【不配平】的比例
  ② 不配平时，差值（缺什么）分布 —— 若集中在 H2O / HCl，说明有统一修法
用法: python diag_retro_balance.py [目标数]
"""
import json
import sys
import time
from collections import Counter
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

STAGE = Path(r"D:\ProgramData\DSHNS\chemreact-staging")
sys.path.insert(0, str(STAGE / "tools"))
sys.path.insert(0, str(STAGE / "libs"))
sys.path.insert(0, r"D:\TCMAI\src")

from rdkit import Chem, RDLogger  # noqa: E402
from rdkit.Chem import Descriptors, rdMolDescriptors  # noqa: E402
from retro_search import load_retro_templates, canon  # noqa: E402

RDLogger.DisableLog("rdApp.*")
OUT = STAGE / "reports" / "retro_balance.json"

TARGETS = [
    "CCNC(C)=O",                                     # 简单酰胺
    "O=C(NCCc1ccc(O)cc1)c1ccccc1O",                  # 水杨酰胺
    "CC(=O)Oc1ccccc1C(=O)O",                         # 阿司匹林（酯）
    "COc1cc(CC=C(C)C)cc(OC)c1O",                     # 丁香酚类（醚）
    "O=C(O)c1ccccc1O",                               # 水杨酸
    "Cn1cnc2c1c(=O)n(C)c(=O)n2C",                    # 咖啡因
    "OC[C@@H]1O[C@@H](O)[C@H](O)[C@@H](O)[C@@H]1O",  # 葡萄糖
    "CC(C)=CCc1c(O)cc(O)c2c(=O)cc(-c3cc(O)c(O)c(CC=C(C)C)c3)oc12",  # 异戊烯基黄酮
]


def atom_vec(m):
    """元素 -> 原子数（含氢）。"""
    v = Counter()
    mh = Chem.AddHs(m)
    for a in mh.GetAtoms():
        v[a.GetSymbol()] += 1
    return v


def diff_name(d):
    """差值向量 -> 可读字符串（正 = 前体侧多出来的）。"""
    return "+".join(f"{el}{n:+d}" for el, n in sorted(d.items()) if n)


def main():
    ts = [Chem.MolFromSmiles(s) for s in TARGETS]
    ts = [(TARGETS[i], m) for i, m in enumerate(ts) if m]
    tmpl = load_retro_templates()
    t0 = time.time()
    print("=" * 92)
    print(f"诊断②b：反转切断的配平情况（{len(ts)} 个目标，模板 {len(tmpl):,}）")
    print("=" * 92)

    stat = Counter()
    diffs = Counter()
    per_type_unbal = Counter()
    per_type_all = Counter()
    examples = []

    for name, m in ts:
        tv = atom_vec(m)
        for t in tmpl:
            try:
                res = t.rxn.RunReactants((m,))
            except Exception:
                continue
            for tup in res[:4]:
                pres = []
                ok = True
                for pm in tup:
                    try:
                        Chem.SanitizeMol(pm)
                    except Exception:
                        ok = False
                        break
                    cs = canon(Chem.MolToSmiles(pm))
                    if not cs:
                        ok = False
                        break
                    pres.append(cs)
                if not ok or not pres:
                    continue
                pv = Counter()
                for ps in pres:
                    pm = Chem.MolFromSmiles(ps)
                    if pm is None:
                        ok = False
                        break
                    pv += atom_vec(pm)
                if not ok:
                    continue
                stat["方案总数"] += 1
                per_type_all[t.name] += 1
                d = Counter(pv)
                d.subtract(tv)
                d = {k: v for k, v in d.items() if v != 0}
                if not d:
                    stat["配平"] += 1
                else:
                    stat["不配平"] += 1
                    per_type_unbal[t.name] += 1
                    ds = diff_name(d)
                    diffs[ds] += 1
                    if len(examples) < 12 and "H2O" not in ds:
                        examples.append((name, t.name, pres, ds))

    print(f"\n方案总数 {stat['方案总数']:,}")
    print(f"   配平   {stat['配平']:>8,}  ({stat['配平']/max(stat['方案总数'],1)*100:5.1f}%)")
    print(f"   不配平 {stat['不配平']:>8,}  ({stat['不配平']/max(stat['方案总数'],1)*100:5.1f}%)")
    print("\n不配平的差值分布（前 20）:")
    for k, v in diffs.most_common(20):
        print(f"   {v:>7,}  {k[:60]}")

    print("\n不配平率最高的反应类型（方案数>=100）:")
    rows = sorted(((per_type_unbal[k] / per_type_all[k], per_type_unbal[k], per_type_all[k], k)
                   for k in per_type_all if per_type_all[k] >= 100), reverse=True)
    for r, b, a, k in rows[:15]:
        print(f"   {r*100:5.1f}%   {b:>6}/{a:<6} {k}")

    print("\n不配平例子（非水）:")
    for name, tn, pres, ds in examples[:8]:
        print(f"   [{tn}] {name[:30]}")
        print(f"      前体 {pres}  差值 {ds}")

    OUT.write_text(json.dumps({"n_targets": len(ts), "summary": dict(stat),
                               "diff_top": dict(diffs.most_common(50)),
                               "per_type_unbal": dict(per_type_unbal),
                               "per_type_all": dict(per_type_all)},
                              ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n-> {OUT.name}  耗时 {time.time()-t0:.0f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
