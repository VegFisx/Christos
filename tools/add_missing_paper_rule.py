# -*- coding: utf-8 -*-
r"""
把论文的「酯化」补进规则库 —— 以【停用】状态 + 说清理由，而不是静默丢弃。
================================================================

用户原则：不要静默丢数据。论文有 23 条，我库里只有 22 条能对上，
漏的那条必须显式存在并说明为什么不能用。

实测（tools/check_paper_esterification.py）：
    论文【酯化】[OX2H:1][CX4:2][CX3:3](=[OX1:4])[OX2H:5]
              >>[O:1]1[CX4:2][CX3:3](=[OX1:4])[OH:5]1

    乙醇酸 HOCH2COOH → 匹配 1 处，但产物【价态非法】(O 价态 3)
    乳酸             → 同样价态非法
    水杨酸/3-羟基丙酸/4-羟基丁酸 → 一个都不匹配

  → 产物模板的环闭合写法有误，生成不了合法结构。
  → 论文想表达的应是【内酯化】，而正确化学已由
     γ-内酯化 / δ-内酯化 两条规则覆盖。
"""
import json
from pathlib import Path

STAGE = Path(r"D:\ProgramData\DSHNS\chemreact-staging")
F = STAGE / "rules" / "rules.json"

PAPER_SMARTS = ("[OX2H:1][CX4:2][CX3:3](=[OX1:4])[OX2H:5]"
                ">>[O:1]1[CX4:2][CX3:3](=[OX1:4])[OH:5]1")

NOTE = (
    "【论文原版，已停用】这是论文 TableS1 里名为「酯化」的那一条，"
    "23 条中唯一一条本库【未实现】的。实测（tools/check_paper_esterification.py）："
    "它的产物模板 `[O:1]1[CX4:2][CX3:3](=[OX1:4])[OH:5]1` 环闭合写法有误，"
    "在乙醇酸、乳酸等任何能匹配的底物上都生成【价态非法】结构（O 价态 3）；"
    "而水杨酸、3-羟基丙酸、4-羟基丁酸则完全不匹配（模板要求羟基与羧基相邻且都在脂肪碳上）。"
    "论文想表达的是【内酯化】，该化学已由 γ-内酯化 / δ-内酯化 正确覆盖。"
    "保留此条是为了【不静默丢数据】—— 23 条论文规则在本库里都能找到对应记录。"
)

d = json.loads(F.read_text(encoding="utf-8"))
rules = d["rules"]

exists = any(r["id"] == "esterification_paper_original_001" for r in rules)
if exists:
    print("已存在，跳过")
else:
    rules.append({
        "id": "esterification_paper_original_001",
        "name": "酯化(论文原版·产物模板有误)",
        "category": "esterification",
        "smarts": PAPER_SMARTS,
        "reversible": False,
        "co_reagents": {},
        "byproducts": {},
        "condition_profile": "thermal",
        "priority": 0.0,
        "status": "disabled",
        "notes": NOTE,
        "max_products_per_molecule": 1,
    })
    F.write_text(json.dumps(d, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("已补入 1 条（status=disabled）")

# 复查：23 条论文规则现在是否都有对应
import csv
PAPER = Path(r"D:\TCMAI\docs\supplementary\TableS1_reaction_rules.csv")
paper = {}
with PAPER.open(encoding="utf-8-sig") as f:
    for row in csv.DictReader(f):
        paper[row["规则名"].strip()] = row["SMARTS"].strip()

rules = json.loads(F.read_text(encoding="utf-8"))["rules"]
by_name = {r["name"]: r for r in rules}
print()
print("=" * 92)
print("复查：论文 23 条规则在本库的对应情况")
print("=" * 92)
miss = []
for name in paper:
    hit = by_name.get(name)
    if hit is None:
        # 名字不同时，看 SMARTS 是否相同
        hit = next((r for r in rules if r["smarts"].strip() == paper[name]), None)
    if hit is None:
        miss.append(name)
        print(f"  ✗ {name}")
    else:
        print(f"  ✓ {name:<22}{hit['status']:<10}{hit['id']}")
print()
print(f"未对应: {len(miss)} 条 {miss if miss else ''}")
print(f"规则总数 {len(rules)}"
      f"（启用 {sum(1 for r in rules if r.get('status')=='active')}，"
      f"停用 {sum(1 for r in rules if r.get('status')=='disabled')}）")
