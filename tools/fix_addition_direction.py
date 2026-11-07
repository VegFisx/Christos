# -*- coding: utf-8 -*-
r"""修「加成方向写反」这一类 bug，并系统性排查同类。

★★ 这一类 bug 已经出现 4 次 ★★
    1. Michael加成(硫醇)   硫接在 α碳，应在 β碳
    2. Michael加成(胺)     氮接在 α碳，应在 β碳
    3. α,β-不饱和羰基水合   羟基因在 α碳，应在 β碳
    4. （本条待确认）

共同特征：
    · 反应都是「往一个体系里加一个基团」
    · 产物 SMARTS 里，那个基团挂在了【错误的原子】上
    · **原子数完全不变**，所以原子守恒/价态/立体化学/化学合理性全都放行

为什么容易犯：
    写 SMARTS 时，`[C:1]=[C:2][C:3]=[O:4]` 里 C1 是末端、C2 是 α、C3 是羰基碳。
    凭直觉很容易把新基团挂在"看起来更靠中间"的 C2 上。

本脚本：
    A. 修 α,β-不饱和羰基水合
    B. 修 醇醛缩合 的氢数写死问题
    C. 列出所有"加成类"规则，逐条打印产物模板，供人工核对方向
"""
import json
from pathlib import Path

from rdkit import Chem, RDLogger
from rdkit.Chem import AllChem

RDLogger.DisableLog("rdApp.error")
RDLogger.DisableLog("rdApp.warning")

F = Path(r"D:\ProgramData\DSHNS\chemreact-staging\rules\rules.json")
data = json.loads(F.read_text(encoding="utf-8"))
by_id = {r["id"]: r for r in data["rules"]}


def run(smarts, sub, co=None):
    try:
        rxn = AllChem.ReactionFromSmarts(smarts)
    except Exception as e:
        return [f"(编译失败 {e})"]
    mols = [Chem.MolFromSmiles(sub)]
    if co:
        c = Chem.MolFromSmiles(co)
        if c is None:
            return ["(第二反应物解析失败)"]
        mols.append(c)
    try:
        res = rxn.RunReactants(tuple(mols))
    except Exception as e:
        return [f"(运行异常 {e})"]
    outs = set()
    for ps in res[:4]:
        fr = []
        for p in ps:
            pc = Chem.Mol(p)
            try:
                Chem.SanitizeMol(pc)
                fr.append(Chem.MolToSmiles(pc))
            except Exception:
                fr.append("(非法)")
        outs.add(" + ".join(sorted(fr)))
    return sorted(outs)


print("=" * 94)
print("A. 修 α,β-不饱和羰基水合（羟基因在 α碳，应在 β碳）")
print("=" * 94)
OLD = "[C:1]=[C:2][C:3]=[O:4]>>[C:1][C:2]([OH])[C:3]=[O:4]"
NEW = "[C:1]=[C:2][C:3]=[O:4]>>[C:1]([OH])[C:2][C:3]=[O:4]"
for label, sm in (("旧（α-加成，错）", OLD), ("新（β-加成，对）", NEW)):
    print(f"\n  【{label}】{sm}")
    for nm, sub in (("丙烯醛", "C=CC=O"), ("丙烯酸甲酯", "C=CC(=O)OC"),
                    ("2-丁烯醛", "CC=CC=O")):
        print(f"    {nm:<12} → {run(sm, sub)}")

print()
print("  化学依据：α,β-不饱和羰基水合是 Michael 型加成，")
print("            水（OH-）加到【β碳】，质子加到 α碳，得到 β-羟基羰基。")

print()
print("=" * 94)
print("B. 修 醇醛缩合（烯醇碳氢数写死）")
print("=" * 94)
A_OLD = ("[CX3:1](=[OX1:2])[CX4H2:3].[CX3:4](=[OX1:5])[#6:6]"
         ">>[C:1](=[O:2])[C:3][C:4]([OH:5])[#6:6]")
A_NEW = ("[CX3:1](=[OX1:2])[CX4:3].[CX3:4](=[OX1:5])[#6:6]"
         ">>[C:1](=[O:2])[C:3][C:4]([OH:5])[#6:6]")
print(f"  旧: {A_OLD}")
print(f"  新: {A_NEW}")
print("""
  ★ 问题：[CX4H2:3] 要求烯醇碳【恰好 2 个氢】。
     乙醛的 α碳是 CH3（3 个氢）→ 匹配不上。
     于是最经典的「乙醛自身缩合」这条规则做不到。
     而去掉氢数限制后，CH3/CH2/CH 三种都能匹配。
""")
for nm, s1, s2 in (("乙醛+乙醛", "CC=O", "CC=O"), ("丙醛+丙醛", "CCC=O", "CCC=O")):
    print(f"    {nm:<12} 旧={run(A_OLD, s1, s2)}")
    print(f"    {'':<12} 新={run(A_NEW, s1, s2)}")

# ---------------- 应用 ----------------
print()
print("=" * 94)
print("应用修改")
print("=" * 94)
for rid, new, note in (
    ("hydration_enone_001", NEW,
     "★★加成方向修复★★ 羟基因在了 α碳(C2) 上，而 α,β-不饱和羰基水合是 Michael 型加成，"
     "水应加到【β碳】(C1)。原写法给 CC(O)C=O（乳醛），正确应为 O=CCCO（3-羟基丙醛）。"
     "两个产物分子式相同，四道闸门全会放行。这是第 3 个「加基因接错原子」的 bug。"),
    ("condensation_aldol_001", A_NEW,
     "【覆盖修复】原 [CX4H2:3] 要求烯醇碳恰好 2 个氢，"
     "导致乙醛（α碳为 CH3）这个最经典的醛缩合底物匹配不上。"
     "去掉氢数限制后可覆盖 CH3/CH2/CH 三种。"),
):
    r = by_id.get(rid)
    if r is None:
        print(f"  [跳过] {rid}")
        continue
    r["smarts"] = new
    r["notes"] = r.get("notes", "") + " " + note
    print(f"  [修] {r['name']}")
    print(f"       {new}")

F.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

# ---------------- C. 列出所有加成类规则供人工核对方向 ----------------
print()
print("=" * 94)
print("C. 全部「加成/水合」类规则的产物模板 —— 请人工核对方向")
print("=" * 94)
for r in data["rules"]:
    if r.get("status") == "disabled":
        continue
    cat = r.get("category", "")
    if cat not in ("addition", "hydration"):
        continue
    prod = r["smarts"].split(">>")[-1]
    print(f"  {r['name']:<22} {prod}")

print()
print(f"规则总数 {len(data['rules'])}")
