# -*- coding: utf-8 -*-
r"""
论文规则表 vs 现规则库：逐条对照
================================

`docs/supplementary/TableS1_reaction_rules.csv` 是发表时用的 23 条规则表。
本脚本把它和现在的 61 条规则库逐条对齐，回答：

  · 发表的 23 条，现在都还在吗？（有没有被漏掉）
  · 哪些的 SMARTS 被改过？
  · 每条改动，在论文里原本的描述下站得住吗？

★ 这不是"我改得更好"的自证，而是要看清：
  **论文补充材料里的 SMARTS，跟它自己写的说明一致吗？**
"""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

STAGE = Path(r"D:\ProgramData\DSHNS\chemreact-staging")
PAPER = Path(r"D:\TCMAI\docs\supplementary\TableS1_reaction_rules.csv")

for d in ("rules", "libs"):
    p = STAGE / d
    if p.is_dir():
        sys.path.insert(0, str(p))

from schema import load_rules

profiles, rules = load_rules(str(STAGE / "rules" / "rules.json"))

# 读论文表
paper = []
with PAPER.open(encoding="utf-8-sig") as f:
    for row in csv.DictReader(f):
        paper.append(row)

print(f"论文规则表：{len(paper)} 条")
print(f"现规则库：{len(rules)} 条（active {sum(1 for r in rules if r.get('status')!='disabled')}）")
print()

# 用 SMARTS 精确匹配 + 名字匹配双路对齐
by_smarts = {r["smarts"].strip(): r for r in rules}
by_name = {r["name"].strip(): r for r in rules}

# 论文名 → 现库名的别名（改名过的）
ALIAS = {
    "酯化": "γ-内酯化",
}

aligned, renamed, missing = [], [], []
for p in paper:
    name = p["规则名"].strip()
    smarts = p["SMARTS"].strip()
    cur = by_smarts.get(smarts)
    how = "SMARTS 完全一致"
    if cur is None:
        cur = by_name.get(name)
        how = "名字匹配"
    if cur is None and name in ALIAS:
        cur = by_name.get(ALIAS[name])
        how = f"按别名匹配（{ALIAS[name]}）"
    if cur is None:
        missing.append(p)
        continue
    changed = cur["smarts"].strip() != smarts
    if changed:
        renamed.append((p, cur, how))
    else:
        aligned.append((p, cur, how))

print("=" * 100)
print(f"① SMARTS 未被改动的：{len(aligned)} 条")
print("=" * 100)
for p, cur, how in aligned:
    print(f"  {p['规则名']:<20} → {cur['name']:<20} ({how})")

print()
print("=" * 100)
print(f"② ★ SMARTS 被改过的：{len(renamed)} 条 ★")
print("=" * 100)
for p, cur, how in renamed:
    print(f"\n  【{p['规则名']}】论文说明：{p['说明']}")
    print(f"     论文: {p['SMARTS']}")
    print(f"     现在: {cur['smarts']}")
    print(f"     对齐方式: {how}  状态: {cur.get('status')}")

if missing:
    print()
    print("=" * 100)
    print(f"③ ★ 论文里有、现库找不到的：{len(missing)} 条 ★")
    print("=" * 100)
    for p in missing:
        print(f"  {p['规则名']:<20} {p['SMARTS'][:70]}")
        print(f"     说明：{p['说明']}")

print()
print("=" * 100)
print("④ 论文 23 条 vs 现库 61 条")
print("=" * 100)
paper_names = {p["规则名"].strip() for p in paper}
cur_names = {r["name"].strip() for r in rules}
new_rules = sorted(n for n in cur_names if n not in paper_names
                   and n not in ALIAS.values())
print(f"  论文有、现库新增的规则：{len(new_rules)} 条")
for n in new_rules:
    r = by_name[n]
    print(f"    {n:<24}{r.get('category','')}")

# 落盘对照表
out = STAGE / "reports" / "paper_vs_current_rules.md"
lines = ["# 论文规则表 vs 现规则库\n",
         f"- 论文 TableS1：{len(paper)} 条",
         f"- 现规则库：{len(rules)} 条\n",
         f"## SMARTS 未变（{len(aligned)} 条）\n",
         "| 论文名 | 现名 |", "|---|---|"]
for p, cur, _how in aligned:
    lines.append(f"| {p['规则名']} | {cur['name']} |")
lines.append(f"\n## SMARTS 已改（{len(renamed)} 条）\n")
for p, cur, _how in renamed:
    lines.append(f"### {p['规则名']}")
    lines.append(f"- 论文说明：{p['说明']}")
    lines.append(f"- 论文 SMARTS：`{p['SMARTS']}`")
    lines.append(f"- 现行 SMARTS：`{cur['smarts']}`")
    lines.append("")
lines.append(f"\n## 现库新增（{len(new_rules)} 条）\n")
for n in new_rules:
    r = by_name[n]
    lines.append(f"- {n}（{r.get('category','')}）")
out.write_text("\n".join(lines) + "\n", encoding="utf-8")
print(f"\n对照表已写入 {out}")
