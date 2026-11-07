# -*- coding: utf-8 -*-
r"""修反应级测试集记录下来的两条规则覆盖缺口。

★ 缺口一：逆羟醛裂解 —— 中间碳被限定成 CH

    SMARTS: [C:1]([OH:2])[CX4H:3][C:4](=[OX1:5])
                              ^^^^^^ 要求恰好 1 个氢

    β-羟基羰基最典型的形态恰恰是中间为 CH2 ——
    比如醛缩合产物 CH3-CH(OH)-CH2-CHO。
    被 [CX4H:3] 一挡，最常见的底物全部匹配不上。

    改成 [CX4:3]（不限氢数）。

★ 缺口二：酰胺水解 —— 只认 N-取代酰胺，伯酰胺全灭

    SMARTS: [C:1](=[O:2])[N:3][C:4]
                              ^^^^ 要求氮上必须连碳

    于是乙酰胺、谷氨酰胺、天冬酰胺这类伯酰胺（R-CONH2）**一个都水解不了**。
    而伯酰胺在中药里很常见。

    改成 [C:1](=[O:2])[N:3]，让氮上的取代基【不写进模板】——
    未映射的取代基会被原样带到产物里，所以：
        N-甲基乙酰胺 → 乙酸 + 甲胺   （氮上那个甲基自动保留）
        乙酰胺       → 乙酸 + 氨
    一条 SMARTS 覆盖两种。
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
    """跑一条 SMARTS，返回去重后的产物字符串列表。"""
    try:
        rxn = AllChem.ReactionFromSmarts(smarts)
    except Exception as e:
        return [f"(SMARTS 编译失败: {e})"]
    mols = [Chem.MolFromSmiles(sub)]
    if co:
        mols.append(Chem.MolFromSmiles(co))
    try:
        res = rxn.RunReactants(tuple(mols))
    except Exception as e:
        return [f"(运行异常: {e})"]
    outs = set()
    for ps in res[:6]:
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


print("=" * 92)
print("缺口一：逆羟醛裂解")
print("=" * 92)
OLD1 = "[C:1]([OH:2])[CX4H:3][C:4](=[OX1:5])>>[CX3:1]=[OX1:2].[CX3:3][C:4](=[OX1:5])"
NEW1 = "[C:1]([OH:2])[CX4:3][C:4](=[OX1:5])>>[CX3:1]=[OX1:2].[CX3:3][C:4](=[OX1:5])"
SUBS1 = [
    ("乙醛自身缩合产物（中间是 CH2，最典型）", "CC(O)CC=O"),
    ("原来的用例（中间是 CH）", "CC(O)C(C)C=O"),
    ("4-羟基-2-丁酮", "OCCC(C)=O"),
]
for label, sm in (("旧 [CX4H:3]", OLD1), ("新 [CX4:3]", NEW1)):
    print(f"\n【{label}】")
    for name, sub in SUBS1:
        r = run(sm, sub)
        mark = "✓" if r and not r[0].startswith("(") else "✗"
        print(f"  {mark} {name:<34} {r[:1] if r else '(无)'}")

print()
print("=" * 92)
print("缺口二：酰胺水解（伯酰胺 / N-取代酰胺）")
print("=" * 92)
OLD2 = "[C:1](=[O:2])[N:3][C:4]>>[C:1](=[O:2])[OH].[N:3][C:4]"
NEW2 = "[C:1](=[O:2])[N:3]>>[C:1](=[O:2])[OH].[N:3]"
SUBS2 = [
    ("乙酰胺（伯酰胺）", "CC(N)=O"),
    ("N-甲基乙酰胺（N-取代）", "CC(=O)NC"),
    ("乙酰苯胺（N-芳基）", "CC(=O)Nc1ccccc1"),
    ("甘氨酰胺（伯酰胺，带氨基）", "NCC(N)=O"),
]
for label, sm in (("旧 [N:3][C:4]", OLD2), ("新 [N:3]", NEW2)):
    print(f"\n【{label}】")
    for name, sub in SUBS2:
        r = run(sm, sub)
        mark = "✓" if r and not r[0].startswith("(") else "✗"
        print(f"  {mark} {name:<28} {r[:1] if r else '(无)'}")

# ---------------- 应用 ----------------
print()
print("=" * 92)
print("应用修改")
print("=" * 92)
for rid, new, note in (
    ("rearrangement_retro_aldol_001", NEW1,
     "【覆盖修复】原 [CX4H:3] 要求中间碳恰好 1 个氢，"
     "把最典型的 β-羟基羰基（中间为 CH2，如醛缩合产物）全部排除。已放宽为 [CX4:3]。"),
    ("hydrolysis_amide_001", NEW2,
     "【覆盖修复】原 [N:3][C:4] 要求氮上必须连碳，"
     "导致乙酰胺/谷氨酰胺/天冬酰胺等【伯酰胺】一个都水解不了。"
     "改为 [N:3]，氮上取代基不写进模板——未映射的取代基会原样带入产物，"
     "一条 SMARTS 同时覆盖伯酰胺与 N-取代酰胺。"),
):
    r = by_id.get(rid)
    if r is None:
        print(f"  [跳过] {rid}")
        continue
    r["smarts"] = new
    r["notes"] = (r.get("notes", "") + " " + note)
    print(f"  [修] {r['name']}")
    print(f"       {new}")

F.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(f"\n规则总数 {len(data['rules'])}")
