# -*- coding: utf-8 -*-
r"""
新旧引擎影响量化：论文版 SMARTS vs 现行版 SMARTS
================================================

方法：
  1. 从 admet_products_all.csv 取出【旧引擎实际作用过的】(母体成分, 规则) 记录
  2. 从 tcm.db 查每个母体的 isomeric SMILES
  3. 分别用【论文版 SMARTS】和【现行版 SMARTS】跑同一个母体
  4. 比较产物集合：多了什么、少了什么、变了什么

这回答的是最实际的问题：**这些修正，到底改变了多少结果？**
"""

from __future__ import annotations

import csv
import json
import sqlite3
import sys
from collections import Counter, defaultdict
from pathlib import Path

STAGE = Path(r"D:\ProgramData\DSHNS\chemreact-staging")
OLD_CSV = Path(r"D:\TCMAI\docs\reports\admet_products_all.csv")
PAPER = Path(r"D:\TCMAI\docs\supplementary\TableS1_reaction_rules.csv")
DB = r"D:\TCMAI\tcm.db"

for d in ("rules", "libs"):
    p = STAGE / d
    if p.is_dir():
        sys.path.insert(0, str(p))

from rdkit import Chem, RDLogger
from rdkit.Chem import AllChem

RDLogger.DisableLog("rdApp.error")
RDLogger.DisableLog("rdApp.warning")

from schema import load_rules

profiles, rules = load_rules(str(STAGE / "rules" / "rules.json"))
cur_by_name = {r["name"]: r for r in rules}

# 论文版 SMARTS
paper_smarts = {}
with PAPER.open(encoding="utf-8-sig") as f:
    for row in csv.DictReader(f):
        paper_smarts[row["规则名"].strip()] = row["SMARTS"].strip()

# 旧引擎实际作用过的 (母体, 规则)
used = defaultdict(set)
with OLD_CSV.open(encoding="utf-8-sig", newline="") as f:
    for row in csv.DictReader(f):
        used[row["rxn"].strip()].add(row["from_compound"].strip())

print(f"旧引擎用到的规则 {len(used)} 条")
for k, v in sorted(used.items(), key=lambda x: -len(x[1])):
    print(f"    {k:<24}{len(v):>6} 个母体")

# 查 SMILES
conn = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
cur = conn.cursor()


def smiles_of(name):
    cur.execute(
        "SELECT isomeric_smiles, smiles FROM compounds WHERE name_en LIKE ? LIMIT 1",
        (name,))
    row = cur.fetchone()
    if not row:
        return None
    return (row[0] or row[1] or "").strip() or None


def products(smarts, sub_smi, limit=8):
    try:
        rxn = AllChem.ReactionFromSmarts(smarts)
    except Exception:
        return None
    m = Chem.MolFromSmiles(sub_smi)
    if m is None:
        return None
    n_react = rxn.GetNumReactantTemplates()
    if n_react != 1:
        return None
    try:
        res = rxn.RunReactants((m,))
    except Exception:
        return set()
    out = set()
    for ps in res[:limit]:
        fr = []
        ok = True
        for p in ps:
            pc = Chem.Mol(p)
            try:
                Chem.SanitizeMol(pc)
                # ★ 必须把显式氢归一化再比 ★
                #   论文版有 [O:3][H] 这种写法，产物里会留下一个显式 H 原子节点，
                #   于是 [H]OC(C)=O 和 CC(=O)O 被当成两个不同的分子。
                #   它们其实是同一个。不去掉显式氢，比出来的差异全是假的。
                pc = Chem.RemoveHs(pc)
                fr.append(Chem.MolToSmiles(pc))
            except Exception:
                ok = False
                break
        if ok:
            out.add(tuple(sorted(fr)))
    return out


print()
print("=" * 104)
print("逐规则影响（只统计【SMARTS 有改动】的规则）")
print("=" * 104)

CHANGED = ["酯水解", "糖苷水解", "酰胺水解", "缩醛水解", "醌还原",
           "α,β-不饱和羰基水合", "脱水", "脱甲基", "酮-烯醇化", "β-酮酸脱羧"]

summary = []
for name in CHANGED:
    cur_rule = cur_by_name.get(name)
    old_sm = paper_smarts.get(name)
    if cur_rule is None or old_sm is None:
        continue
    new_sm = cur_rule["smarts"].strip()
    if old_sm == new_sm:
        continue

    comps = sorted(used.get(name, []))
    n_checked = 0
    gained = lost = changed = same = 0
    no_smi = 0
    ex_gain = ex_lost = ex_changed = None

    for comp in comps[:400]:
        smi = smiles_of(comp)
        if not smi:
            no_smi += 1
            continue
        po = products(old_sm, smi)
        pn = products(new_sm, smi)
        if po is None or pn is None:
            continue
        n_checked += 1
        if po == pn:
            same += 1
            continue
        # 归类：只在旧版出现 / 只在新版出现 / 两者都有但集合不同
        only_old = po - pn
        only_new = pn - po
        if only_new and not only_old:
            gained += 1
            ex_gain = ex_gain or (comp, sorted(only_new)[0])
        elif only_old and not only_new:
            lost += 1
            ex_lost = ex_lost or (comp, sorted(only_old)[0])
        else:
            changed += 1
            ex_changed = ex_changed or (comp, sorted(only_old)[0], sorted(only_new)[0])

    summary.append((name, len(comps), n_checked, same, gained, lost, changed, no_smi,
                    ex_gain, ex_lost, ex_changed))
    print(f"\n【{name}】旧引擎作用过 {len(comps)} 个母体，实际比对 {n_checked} 个")
    print(f"    产物完全一致 : {same}")
    print(f"    只在新版出现 : {gained}   ← 修好了漏匹配")
    print(f"    只在旧版出现 : {lost}   ← 收窄了范围")
    print(f"    两边都有但不同: {changed}   ← 产物结构被改")
    if ex_gain:
        print(f"      例（新增） {ex_gain[0][:36]} → {ex_gain[1][:56]}")
    if ex_lost:
        print(f"      例（消失） {ex_lost[0][:36]} → {ex_lost[1][:56]}")
    if ex_changed:
        print(f"      例（改了） {ex_changed[0][:36]}")
        print(f"                  旧 {ex_changed[1][:60]}")
        print(f"                  新 {ex_changed[2][:60]}")

print()
print("=" * 104)
print("汇总")
print("=" * 104)
print(f"{'规则':<22}{'母体':>6}{'比对':>6}{'一致':>6}{'新增':>6}{'消失':>6}{'改变':>6}")
print("-" * 66)
tot = Counter()
for (name, n_comp, n_chk, same, g, l, c, ns, *_rest) in summary:
    print(f"{name:<22}{n_comp:>6}{n_chk:>6}{same:>6}{g:>6}{l:>6}{c:>6}")
    tot["comp"] += n_comp
    tot["chk"] += n_chk
    tot["same"] += same
    tot["g"] += g
    tot["l"] += l
    tot["c"] += c
print("-" * 66)
print(f"{'合计':<22}{tot['comp']:>6}{tot['chk']:>6}{tot['same']:>6}"
      f"{tot['g']:>6}{tot['l']:>6}{tot['c']:>6}")
print()
if tot["chk"]:
    diff = tot["g"] + tot["l"] + tot["c"]
    print(f"  有差异的母体：{diff} / {tot['chk']} = {100*diff/tot['chk']:.1f}%")
print(f"  查不到 SMILES 的母体：{sum(x[7] for x in summary)}")

conn.close()
