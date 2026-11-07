# -*- coding: utf-8 -*-
r"""
新旧引擎正面对比：同一批真实药材成分，各跑一遍
================================================

★ 实验设计

  旧引擎 `_valid_product(mol, min_mw=100, min_heavy=10)` 会直接删掉小分子。
  如果只跟新引擎（保留小分子）比，差异里混了两种原因。
  所以分两种模式跑新引擎：

    模式 A  legacy_filter=True   复刻旧的过滤器 → 差异【只来自规则】
    模式 B  legacy_filter=False  新版过滤器     → 差异 = 规则 + 过滤器

  这样能把两个原因分离出来。

★ 差异分类

  对每个差异产物，标出它属于哪一类原因：
    · 规则新增       新库多出来的规则产生
    · 规则修正       SMARTS 改过（加成方向/漏匹配/产物片段）
    · 过滤器保留     小分子被保留（旧版会删）
    · 未归类         需要人工看
"""

from __future__ import annotations

import json
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

STAGE = Path(r"D:\ProgramData\DSHNS\chemreact-staging")
TCMAI_SRC = Path(r"D:\TCMAI\src")

sys.path.insert(0, str(TCMAI_SRC))
sys.path.insert(0, str(STAGE / "api"))
for d in ("core", "conditions", "rules", "libs", "sources"):
    p = STAGE / d
    if p.is_dir():
        sys.path.insert(0, str(p))

from rdkit import Chem, RDLogger
RDLogger.DisableLog("rdApp.error")
RDLogger.DisableLog("rdApp.warning")

import tcm_analyzer                     # 旧引擎（只读导入）
import compat                           # 新引擎兼容层


def canon(smi):
    m = Chem.MolFromSmiles(smi) if smi else None
    return Chem.MolToSmiles(m) if m else None


# ---------------------------------------------------------------- 论文版 SMARTS
PAPER = Path(r"D:\TCMAI\docs\supplementary\TableS1_reaction_rules.csv")
import csv
paper_smarts = {}
with PAPER.open(encoding="utf-8-sig") as f:
    for row in csv.DictReader(f):
        paper_smarts[row["规则名"].strip()] = row["SMARTS"].strip()

# 新库里改动过的规则（名字 → 是否改过）
NEW_RULES = {r["name"]: r for r in
             json.loads((STAGE / "rules" / "rules.json").read_text(encoding="utf-8"))["rules"]}
CHANGED = {n for n, r in NEW_RULES.items()
           if n in paper_smarts and paper_smarts[n] != r["smarts"].strip()}
NEW_ONLY = {n for n in NEW_RULES if n not in paper_smarts}


def run_one(name, compounds, **kw):
    t0 = time.time()
    ps = compat.predict_reactions(compounds, **kw)
    return ps, time.time() - t0


def main() -> int:
    from tcm_ro import use_readonly; use_readonly()
    from db_utils import find_compounds

    HERBS = ["甘草", "附子", "干姜"]
    per = 20
    print(f"新旧引擎正面对比 · 药材 {HERBS} 各 {per} 个成分")
    print()

    all_comps = []
    for h in HERBS:
        rows = find_compounds(h, limit=per)
        all_comps.extend(rows)
    print(f"合计成分 {len(all_comps)} 个")
    print()

    # ---- 旧引擎 ----
    t0 = time.time()
    old = tcm_analyzer.predict_reactions(all_comps)
    old_dt = time.time() - t0
    old_set = {}
    for p in old:
        key = canon(p["smiles"])
        if key:
            old_set.setdefault(key, p)

    # ---- 新引擎 模式 A：复刻旧过滤器 ----
    newA, dtA = run_one("A", all_comps, legacy_filter=True)
    setA = {}
    for p in newA:
        key = canon(p["smiles"])
        if key:
            setA.setdefault(key, p)

    # ---- 新引擎 模式 B：新版过滤器 ----
    newB, dtB = run_one("B", all_comps, legacy_filter=False)
    setB = {}
    for p in newB:
        key = canon(p["smiles"])
        if key:
            setB.setdefault(key, p)

    # ---- 新引擎 模式 C：★全规则激活★（同口径对比） ----
    # 旧引擎没有条件层，23 条规则永远全跑。
    # 新版默认按工艺门控，所以直接比会把「条件差异」混进「规则差异」。
    # 阈值设 0 让 58 条全部激活，得到同口径对比。
    newC, dtC = run_one("C", all_comps, legacy_filter=True, threshold=0.0)
    setC = {}
    for p in newC:
        key = canon(p["smiles"])
        if key:
            setC.setdefault(key, p)

    print("=" * 100)
    print("① 总量")
    print("=" * 100)
    print(f"  旧引擎                 {len(old):>5} 个产物（去重后 {len(old_set)}）  {old_dt:.1f}s")
    print(f"  新引擎 [复刻旧过滤器]    {len(newA):>5} 个产物（去重后 {len(setA)}）  {dtA:.1f}s")
    print(f"  新引擎 [新版过滤器]      {len(newB):>5} 个产物（去重后 {len(setB)}）  {dtB:.1f}s")
    print(f"  新引擎 [★全规则激活★]   {len(newC):>5} 个产物（去重后 {len(setC)}）  {dtC:.1f}s")
    print()
    print("  ★ 为什么要有「全规则激活」这一档 ★")
    print("     旧引擎没有条件层——23 条规则永远全跑。")
    print("     新版默认按工艺门控（煎煮下只激活 42/58 条）。")
    print("     直接比会把「条件差异」混进「规则差异」。")
    print("     阈值设 0 让 58 条全激活，才是同口径。")
    print()

    print("=" * 100)
    print("①b 同口径对比（新引擎全规则激活 vs 旧引擎）")
    print("=" * 100)
    oo2 = {k: v for k, v in old_set.items() if k not in setC}
    on2 = {k: v for k, v in setC.items() if k not in old_set}
    print(f"  两边都有 : {len(set(old_set) & set(setC))}")
    print(f"  只有旧引擎: {len(oo2)}")
    print(f"  只有新引擎: {len(on2)}")
    print(f"  只有旧引擎的规则分布:")
    for r, n in Counter(p["rxn"] for p in oo2.values()).most_common(10):
        print(f"      {r:<22}{n:>5}  {'★SMARTS 改过' if r in CHANGED else ''}")
    print()

    print("=" * 100)
    print("② 只有一边有的产物（模式 A，仅规则差异）")
    print("=" * 100)
    only_old = {k: v for k, v in old_set.items() if k not in setA}
    only_new = {k: v for k, v in setA.items() if k not in old_set}
    both = set(old_set) & set(setA)
    print(f"  两边都有 : {len(both)}")
    print(f"  只有旧引擎: {len(only_old)}")
    print(f"  只有新引擎: {len(only_new)}")

    # 归类「只有新引擎」的产物
    cat = Counter()
    examples = defaultdict(list)
    for k, p in only_new.items():
        r = p["rxn"]
        if r in NEW_ONLY:
            c = "新库新增规则"
        elif r in CHANGED:
            c = "SMARTS 被修正（漏匹配/方向/产物片段）"
        else:
            c = "同一规则但产物不同"
        cat[c] += 1
        if len(examples[c]) < 4:
            examples[c].append(f"{r:<18}{p['formula']:<12}{p['smiles'][:44]}")

    for c, n in cat.most_common():
        print(f"\n  【{c}】{n} 个")
        for e in examples[c]:
            print(f"      {e}")

    print()
    print("=" * 100)
    print("③ 只有旧引擎有的产物（新引擎不再产出）")
    print("=" * 100)
    oldonly_by_rule = Counter(p["rxn"] for p in only_old.values())
    for r, n in oldonly_by_rule.most_common(12):
        tag = "★SMARTS 改过" if r in CHANGED else ""
        print(f"    {r:<22}{n:>5}  {tag}")
    print()
    print("  例：")
    for k, p in list(only_old.items())[:6]:
        print(f"    {p['rxn']:<18}{p['formula']:<12}{p['smiles'][:52]}")

    print()
    print("=" * 100)
    print("④ 过滤器的影响（模式 A vs B）")
    print("=" * 100)
    onlyB = {k: v for k, v in setB.items() if k not in setA}
    print(f"  新版过滤器额外保留: {len(onlyB)} 个小分子（旧版会直接删）")
    for k, p in list(onlyB.items())[:12]:
        print(f"    {p['formula']:<12}{p['rxn']:<18}{p['smiles'][:40]}")

    print()
    print("=" * 100)
    print("⑤ 逐规则产物数对比")
    print("=" * 100)
    c_old = Counter(p["rxn"] for p in old)
    c_new = Counter(p["rxn"] for p in newA)
    names = sorted(set(c_old) | set(c_new), key=lambda n: -(c_new.get(n, 0) + c_old.get(n, 0)))
    print(f"  {'规则':<24}{'旧':>6}{'新':>6}   备注")
    print("  " + "-" * 74)
    for n in names:
        o, w = c_old.get(n, 0), c_new.get(n, 0)
        note = ""
        if n in NEW_ONLY:
            note = "新库新增规则"
        elif n in CHANGED:
            note = "★SMARTS 改过"
        elif o and not w:
            note = "新引擎不再产出"
        print(f"  {n:<24}{o:>6}{w:>6}   {note}")

    # 落盘
    out = STAGE / "reports" / "新旧引擎正面对比.md"
    lines = [
        "# 新旧引擎正面对比（同一批真实药材成分）",
        "",
        f"- 药材：{'、'.join(HERBS)}，各 {per} 个成分，合计 {len(all_comps)}",
        f"- 旧引擎：{len(old_set)} 个去重产物（{old_dt:.1f}s）",
        f"- 新引擎（复刻旧过滤器）：{len(setA)} 个（{dtA:.1f}s）",
        f"- 新引擎（新版过滤器）：{len(setB)} 个（{dtB:.1f}s）",
        "",
        "## 差异（仅规则差异，模式 A）",
        f"- 两边都有：{len(both)}",
        f"- 只有旧引擎：{len(only_old)}",
        f"- 只有新引擎：{len(only_new)}",
        "",
        "### 只有新引擎有的产物，按原因分类",
        "",
        "| 原因 | 个数 |",
        "|---|---|",
    ]
    for c, n in cat.most_common():
        lines.append(f"| {c} | {n} |")
    lines.append("")
    lines.append("### 只有旧引擎有的产物，按规则")
    lines.append("")
    lines.append("| 规则 | 个数 | 备注 |")
    lines.append("|---|---|---|")
    for r, n in oldonly_by_rule.most_common(20):
        lines.append(f"| {r} | {n} | {'SMARTS 改过' if r in CHANGED else ''} |")
    lines.append("")
    lines.append("### 逐规则对比")
    lines.append("")
    lines.append("| 规则 | 旧 | 新 | 备注 |")
    lines.append("|---|---|---|---|")
    for n in names:
        note = ("新库新增规则" if n in NEW_ONLY
                else "SMARTS 改过" if n in CHANGED
                else "新引擎不再产出" if (c_old.get(n, 0) and not c_new.get(n, 0)) else "")
        lines.append(f"| {n} | {c_old.get(n, 0)} | {c_new.get(n, 0)} | {note} |")
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"\n报告已写入 {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
