# -*- coding: utf-8 -*-
r"""修醌还原（产物该芳香化 + 试剂被灌多了），并扫描同类"靠灌试剂凑平"的规则。

★★ 这是「靠调试剂把原子数凑平」的第三次出现 ★★
    第 1 次：美拉德简化，被推导器覆盖成 by={H2:1}（假脱氢）
    第 2 次：分子内脱水成醚，by={H2:1} 填平一个 O-O 键的错
    第 3 次（本次）：醌还原，co={H2:2} 把 4 电子还原伪装成 2 电子

【为什么校验器发现不了】
    校验器的判据是「底物原子 + co原子 == 产物原子 + by原子」。
    把 co 调大，左边就变大，等式自然成立。
    **它只保证「账平」，不保证「账目真实」。**

【本次的正确答案】
    邻苯醌 C6H4O2 + H2 → 邻苯二酚 C6H6O2（芳香）
    产物 SMARTS 的 C2/C3 应写成芳香碳 [c:2]/[c:3]，RDKit 自动芳香化：
        [O:1]=[C:2][C:3]=[O:4]>>[OH:1][c:2][c:3][OH:4]
    这样 co 只需 1 个 H2。

【顺带修】
    酮-烯醇化：[CX4H2:3] 要求 α碳恰好 2 个氢，丙酮（CH3）匹配不上。
"""
import json
import re
from pathlib import Path

from rdkit import Chem, RDLogger
from rdkit.Chem import AllChem, rdMolDescriptors

RDLogger.DisableLog("rdApp.error")
RDLogger.DisableLog("rdApp.warning")

F = Path(r"D:\ProgramData\DSHNS\chemreact-staging\rules\rules.json")
data = json.loads(F.read_text(encoding="utf-8"))
by_id = {r["id"]: r for r in data["rules"]}


def run(smarts, sub):
    rxn = AllChem.ReactionFromSmarts(smarts)
    m = Chem.MolFromSmiles(sub)
    outs = set()
    for ps in rxn.RunReactants((m,))[:3]:
        fr = []
        for p in ps:
            pc = Chem.Mol(p)
            try:
                Chem.SanitizeMol(pc)
                fr.append(f"{Chem.MolToSmiles(pc)}({rdMolDescriptors.CalcMolFormula(pc)})")
            except Exception:
                fr.append("(非法)")
        outs.add(" + ".join(sorted(fr)))
    return sorted(outs)


print("=" * 94)
print("① 醌还原：芳香化 + 试剂改回 1 个 H2")
print("=" * 94)
Q_OLD = "[O:1]=[C:2][C:3]=[O:4]>>[OH:1][C:2][C:3][OH:4]"
Q_NEW = "[O:1]=[C:2][C:3]=[O:4]>>[OH:1][c:2][c:3][OH:4]"
SUBQ = "O=C1C=CC=CC1=O"
for label, sm, co in (("旧 (co=H2:2)", Q_OLD, {"H2": 2}),
                      ("新 (co=H2:1)", Q_NEW, {"H2": 1})):
    print(f"\n  【{label}】{sm}")
    print(f"     底物 C6H4O2 + co={co}")
    print(f"     产物 {run(sm, SUBQ)}")

print()
print("  化学依据：邻苯醌 → 邻苯二酚是 2 电子还原，只需 1 个 H2。")
print("           产物是【芳香】的邻苯二酚 C6H6O2，不是环己二烯二醇 C6H8O2。")

print()
print("=" * 94)
print("② 酮-烯醇化：氢数写死")
print("=" * 94)
K_OLD = "[CX3:1](=[OX1:2])[CX4H2:3]>>[C:1]([OH:2])=[C:3]"
K_NEW = "[CX3:1](=[OX1:2])[CX4:3]>>[C:1]([OH:2])=[C:3]"
for label, sm in (("旧 [CX4H2:3]", K_OLD), ("新 [CX4:3]", K_NEW)):
    print(f"\n  【{label}】")
    for nm, sub in (("丙酮", "CC(C)=O"), ("乙醛", "CC=O"), ("环己酮", "O=C1CCCCC1")):
        print(f"     {nm:<8} → {run(sm, sub)}")

# ---------------- 应用 ----------------
print()
print("=" * 94)
print("应用修改")
print("=" * 94)
APPLY = [
    ("reduction_quinone_001", Q_NEW,
     "★★产物修复★★ 原来产物写成 [OH:1][C:2][C:3][OH:4]，碳氧双键变单键后 "
     "C2/C3 各补 1 个氢，产物成了环己二烯二醇 C6H8O2（非芳香）。"
     "而邻苯醌还原应得到【芳香】的邻苯二酚 C6H6O2。"
     "更糟的是：规则靠把 co_reagents 从 H2:1 灌到 H2:2 让等式成立——"
     "这是「靠调试剂把原子数凑平」，校验器只能看到账平、看不到账假。"
     "已把产物改为芳香碳 [c:2]/[c:3]，co 恢复为 H2:1。"
     "★这是本项目第三次遇到「靠灌试剂凑平」：美拉德简化、分子内脱水成醚、本次。"),
    ("tautomerization_keto_enol_001", K_NEW,
     "【覆盖修复】原 [CX4H2:3] 要求 α碳恰好 2 个氢，"
     "丙酮（α碳为 CH3）这个最典型的底物匹配不上。已去掉氢数限制。"),
]
for rid, new, note in APPLY:
    r = by_id.get(rid)
    if r is None:
        print(f"  [跳过] {rid}")
        continue
    r["smarts"] = new
    r["notes"] = r.get("notes", "") + " " + note
    print(f"  [修] {r['name']}")

# 醌还原的 co 单独改
by_id["reduction_quinone_001"]["co_reagents"] = {"H2": 1}
print(f"  [修] 醌还原 co_reagents → {{'H2': 1}}")

F.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

# ---------------- 扫描可疑的 co_reagents ----------------
print()
print("=" * 94)
print("③ 扫描：co_reagents/byproducts 用量偏大的规则（可能需要人工看）")
print("=" * 94)
print("  判据：单次反应要消耗/产出 2 个以上同种小分子，值得复核是不是在凑账\n")
sus = []
for r in data["rules"]:
    if r.get("status") == "disabled":
        continue
    for field, tag in (("co_reagents", "消耗"), ("byproducts", "产出")):
        for formula, n in (r.get(field) or {}).items():
            if n >= 2:
                sus.append((n, r["name"], tag, formula, r["id"]))
for n, name, tag, formula, rid in sorted(sus, reverse=True):
    print(f"  {tag} {formula} × {n}   {name:<22} {rid}")
if not sus:
    print("  （无）")
print(f"\n  共 {len(sus)} 处待复核")
print(f"\n规则总数 {len(data['rules'])}")
