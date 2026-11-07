# -*- coding: utf-8 -*-
r"""
核对：规则库里的 SMARTS，与【论文 TableS1】的关系。
====================================================

用户要求：数据要用数据库/原始来源，不要手写。

对 23 条论文规则来说，「原始来源」就是
    D:\TCMAI\docs\supplementary\TableS1_reaction_rules.csv

本脚本逐条核对：
  · 哪几条与论文【完全一致】（说明我没动过，来源可靠）
  · 哪几条【我改过】（应该都有明确理由 + 测试守着）
  · 有没有论文里根本没有、我也说不清来源的
"""
import csv
import json
import sys
from pathlib import Path

STAGE = Path(r"D:\ProgramData\DSHNS\chemreact-staging")
PAPER = Path(r"D:\TCMAI\docs\supplementary\TableS1_reaction_rules.csv")

paper = {}
with PAPER.open(encoding="utf-8-sig") as f:
    for row in csv.DictReader(f):
        paper[row["规则名"].strip()] = row["SMARTS"].strip()

rules = json.loads((STAGE / "rules" / "rules.json").read_text(encoding="utf-8"))["rules"]
by_name = {r["name"]: r for r in rules}

print("=" * 104)
print(f"论文 TableS1 有 {len(paper)} 条规则")
print("=" * 104)

same, changed, missing = [], [], []
for name, sm in paper.items():
    r = by_name.get(name)
    if r is None:
        missing.append(name)
        continue
    if r["smarts"].strip() == sm:
        same.append(name)
    else:
        changed.append((name, sm, r["smarts"].strip(), r.get("status"),
                        bool(r.get("notes"))))

print(f"\n【与论文完全一致】{len(same)} 条  ← 来源可靠，未改动")
for n in same:
    print(f"    ✓ {n}")

print(f"\n【我改过】{len(changed)} 条  ← 每条都该有理由和测试")
print(f"  {'规则':<22}{'状态':<10}{'有注释说明':<12}")
print("  " + "-" * 48)
for n, old, new, st, has_note in changed:
    print(f"  {n:<22}{str(st):<10}{'有' if has_note else '★无★':<12}")

print(f"\n【论文有、我库里没有】{len(missing)} 条")
for n in missing:
    print(f"    ✗ {n}")

# 新增的规则：论文里没有的
new_rules = [(r["name"], r["id"], r.get("status"))
             for r in rules if r["name"] not in paper]
print()
print("=" * 104)
print(f"我在论文之外新增的规则：{len(new_rules)} 条")
print("=" * 104)
print("  ★ 这些规则的 SMARTS 是我写的，数据库里没有 —— 必须靠测试守住 ★")
for n, i, st in sorted(new_rules, key=lambda x: x[2] or ""):
    print(f"    [{st:<8}] {n:<22}{i}")

print()
print("=" * 104)
print("结论")
print("=" * 104)
print(f"""
  · 论文 23 条：{len(same)} 条原样保留 + {len(changed)} 条修正 = {len(same)+len(changed)} 条
  · 论文之外新增：{len(new_rules)} 条（SMARTS 无外部来源，只能靠测试）
  · 合计 {len(rules)} 条 ✓

  ★ 用户指出的问题在【另一处】★
    规则 SMARTS 是化学知识，论文只给了 23 条，其余只能自己写 —— 这部分情有可原。
    但【测试用例的底物分子】不该手写 —— 目标是「真实底物用例」，
    应该从 tcm.db 取真实药材成分。
""")
