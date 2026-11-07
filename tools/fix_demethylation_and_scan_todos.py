# -*- coding: utf-8 -*-
r"""修「脱甲基」过宽（备注里早写了警告却没修），并扫描全库未处理的警告。

★ bug 十：脱甲基命中一切 O-CH3
    SMARTS: [O:1][CH3:2]>>[O:1][H].[CH3][OH]
    对乙酸甲酯/苯甲酸甲酯/甲基葡萄糖苷都生效——
    但那些是【酯水解】【糖苷水解】该干的事。
    同一转化被两条规则重复计算，产物溯源会指错规则。

    修法：[O:1][CH3:2] → [c:3][O:1][CH3:2]（氧必须连在芳香碳上）
    这才是中药里真正相关的反应（阿魏酸→咖啡酸、愈创木酚型脱甲基）。

★ 更值得注意的：规则自己的 notes 里早就写着
    「⚠️ SMARTS [O:1][CH3:2] 过宽，会命中脂肪族甲氧基，应加芳香性约束。」
    但从没修过。

    所以本脚本顺带做一件事：**扫全库 notes，找出所有"写了警告却没收尾"的规则。**
    这类 TODO 会一直躺在那里，看起来"已知"，实际没人管。
"""
import json
import re
from pathlib import Path

from rdkit import Chem, RDLogger
from rdkit.Chem import AllChem
from rdkit.Chem.rdMolDescriptors import CalcMolFormula

RDLogger.DisableLog("rdApp.error")
RDLogger.DisableLog("rdApp.warning")

F = Path(r"D:\ProgramData\DSHNS\chemreact-staging\rules\rules.json")
data = json.loads(F.read_text(encoding="utf-8"))
by_id = {r["id"]: r for r in data["rules"]}

print("=" * 96)
print("A. 修脱甲基：加上芳香性约束")
print("=" * 96)
D_OLD = "[O:1][CH3:2]>>[O:1][H].[CH3][OH]"
D_NEW = "[c:3][O:1][CH3:2]>>[c:3][O:1][H].[CH3][OH]"

SUBS = [
    ("苯甲醚（应匹配）", "COc1ccccc1"),
    ("愈创木酚（应匹配）", "COc1ccccc1O"),
    ("丁香酚型（应匹配）", "COc1cc(CC=C)ccc1O"),
    ("甲醇（不该匹配）", "CO"),
    ("乙酸甲酯（不该匹配，属酯水解）", "COC(C)=O"),
    ("苯甲酸甲酯（不该匹配）", "COC(=O)c1ccccc1"),
    ("甲基葡萄糖苷（不该匹配，属糖苷水解）",
     "CO[C@H]1O[C@@H](CO)[C@H](O)[C@@H](O)[C@@H]1O"),
]
for label, sm in (("旧（过宽）", D_OLD), ("新（限芳香）", D_NEW)):
    print(f"\n  【{label}】{sm}")
    rxn = AllChem.ReactionFromSmarts(sm)
    for nm, sub in SUBS:
        m = Chem.MolFromSmiles(sub)
        res = rxn.RunReactants((m,))
        if res:
            fr = []
            for p in res[0]:
                pc = Chem.Mol(p)
                try:
                    Chem.SanitizeMol(pc)
                    fr.append(f"{Chem.MolToSmiles(pc)}({CalcMolFormula(pc)})")
                except Exception:
                    fr.append("(非法)")
            print(f"    ✓ {nm:<34} → {' + '.join(fr)}")
        else:
            print(f"    ✗ {nm:<34} → (不匹配)")

r = by_id.get("demethylation_aromatic_001")
if r:
    r["smarts"] = D_NEW
    r["notes"] = ("★★已修★★ 【芳香甲醚脱甲基】阿魏酸→咖啡酸、愈创木酚型脱甲基，"
                  "是中药里真实相关的反应。"
                  "原 SMARTS [O:1][CH3:2] 过宽，会命中一切 O-CH3——"
                  "乙酸甲酯/苯甲酸甲酯/甲基葡萄糖苷都被它「脱甲基」，"
                  "但那些其实是【酯水解】【糖苷水解】该干的事。"
                  "同一转化被两条规则重复计算，产物溯源会指错规则。"
                  "已加芳香性约束 [c:3][O:1][CH3:2]。"
                  "★注意：本条备注里早就写着「过宽，应加芳香性约束」——"
                  "写了警告却一直没修，是这类 TODO 的通病。")
    print(f"\n  [修] 脱甲基 → {D_NEW}")

F.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

# ---------------- B. 扫全库未收尾的警告 ----------------
print()
print("=" * 96)
print("B. 全库扫描：notes 里写了警告/待办的规则")
print("=" * 96)
WARN = re.compile(r"⚠|待修|待确认|应加|应该|过宽|待复核|TODO|需人工|存疑|不严谨|暂")
hits = []
for rr in data["rules"]:
    note = rr.get("notes") or ""
    if WARN.search(note):
        hits.append((rr["name"], rr["id"], rr.get("status"), note))

for name, rid, status, note in hits:
    print(f"\n  【{name}】{rid}  状态={status}")
    # 只打印含警告的那句
    for sent in re.split(r"[。；\n]", note):
        if WARN.search(sent):
            print(f"      ⚠ {sent.strip()[:110]}")

print(f"\n  共 {len(hits)} 条规则的备注里含警告/待办")
print("""
  ★ 这些是「已知但未处理」的清单。
    有的是有意保留的说明（如"已验证"），有的确实是欠账。
    逐条过一遍才知道哪些还要修。
""")
print(f"规则总数 {len(data['rules'])}")
