# -*- coding: utf-8 -*-
r"""修「脱水」的氢数写死（第 4 次同类问题），并系统扫描全库的氢数约束。

★★ 累计发现的失败模式：氢数写死 ★★
    1. 逆羟醛裂解  [CX4H:3]   排除中间为 CH2 的 β-羟基羰基
    2. 醇醛缩合    [CX4H2:3]  排除乙醛（α碳为 CH3）
    3. 酮-烯醇化   [CX4H2:3]  排除丙酮（α碳为 CH3）
    4. 脱水        [CH2:1][CH1:2]  排除乙醇、1-丙醇等伯醇

    共同特征：反应物模板里对某个碳【写死了氢数】，
    而氢数在真实底物里是可变的。写 SMARTS 时凭"我脑子里那个例子"定了氢数，
    结果只有那一种底物能匹配。

本脚本：
    A. 修脱水
    B. 扫出全库所有 [#X4H<n>:] 形式的氢数约束，逐条列出供复查
"""
import json
import re
from pathlib import Path

from rdkit import Chem, RDLogger
from rdkit.Chem import AllChem

RDLogger.DisableLog("rdApp.error")
RDLogger.DisableLog("rdApp.warning")

F = Path(r"D:\ProgramData\DSHNS\chemreact-staging\rules\rules.json")
data = json.loads(F.read_text(encoding="utf-8"))
by_id = {r["id"]: r for r in data["rules"]}


def run(smarts, sub):
    try:
        rxn = AllChem.ReactionFromSmarts(smarts)
    except Exception as e:
        return [f"(编译失败 {e})"]
    m = Chem.MolFromSmiles(sub)
    try:
        res = rxn.RunReactants((m,))
    except Exception as e:
        return [f"(异常 {e})"]
    outs = set()
    for ps in res[:3]:
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


print("=" * 96)
print("A. 修「脱水」——让伯醇也能脱水成端烯")
print("=" * 96)
D_OLD = "[CH2:1][CH1:2][OH:3]>>[C:1]=[C:2].[OH2]"
D_NEW = "[CX4:1][CX4:2][OX2H:3]>>[C:1]=[C:2].[OH2]"
SUBS = [("乙醇（伯醇）", "CCO"), ("1-丙醇", "CCCO"), ("2-丙醇", "CC(C)O"),
        ("2-丁醇", "CCC(C)O"), ("叔丁醇（应无α-H）", "CC(C)(C)O"),
        ("环己醇", "OC1CCCCC1")]
for label, sm in (("旧 [CH2:1][CH1:2]", D_OLD), ("新 [CX4:1][CX4:2]", D_NEW)):
    print(f"\n  【{label}】{sm}")
    for nm, sub in SUBS:
        r = run(sm, sub)
        mark = "✓" if r and not r[0].startswith("(") else "✗"
        print(f"    {mark} {nm:<20} {r[:1] if r else '(无)'}")
print("""
  化学依据：醇脱水成烯，伯醇给端烯（乙醇→乙烯），仲醇给内烯（2-丁醇→2-丁烯），
            叔醇无 α-H 不能脱水。原来的写法只认「CH2 邻 CH(OH)」这一种。
""")

# ---------------- 应用 ----------------
r = by_id.get("elimination_dehydration_001")
if r:
    r["smarts"] = D_NEW
    r["notes"] = (r.get("notes", "") +
                  " 【覆盖修复】原 [CH2:1][CH1:2][OH:3] 对两个碳都写死了氢数——"
                  "要求羟基碳恰好 1 个氢、邻碳恰好 2 个氢。"
                  "结果【乙醇】这个最基础的脱水底物匹配不上（CH3CH2OH 两个条件都不满足）。"
                  "已放宽为 [CX4:1][CX4:2][OX2H:3]。这是「氢数写死」的第 4 次："
                  "逆羟醛裂解、醇醛缩合、酮-烯醇化、脱水。")
    print(f"  [修] 脱水 → {D_NEW}")

# ---------------- B. 扫描全库氢数约束 ----------------
print()
print("=" * 96)
print("B. 全库扫描：反应物模板里写死的氢数约束")
print("=" * 96)
print("  判据：反应物侧出现 [CX4H<n>:] / [CH<n>:] / [CX3H<n>:] 等形式，")
print("        氢数在真实底物里往往是可变的，写死就可能漏匹配。\n")

pat = re.compile(r"\[(?:#6|C|c|N|O|S|X\d)?X?\d?H(\d+)?:\d+\]")
found = []
for rr in data["rules"]:
    if rr.get("status") == "disabled":
        continue
    react = rr["smarts"].split(">>")[0]
    for m in re.finditer(r"\[[^\]]*H\d+:\d+\]", react):
        found.append((rr["name"], rr["id"], m.group(0), react))

by_rule = {}
for name, rid, tok, react in found:
    by_rule.setdefault((name, rid), []).append(tok)

print(f"{'规则':<24}{'写死的氢数约束':<34}反应物模板")
print("-" * 96)
for (name, rid), toks in sorted(by_rule.items()):
    react = next(x[3] for x in found if x[1] == rid)
    print(f"{name:<24}{' '.join(sorted(set(toks))):<34}{react[:40]}")

print(f"\n  共 {len(by_rule)} 条规则含写死的氢数约束，需要逐条判断「是有意还是过窄」")
print("""
  判断标准：
    · 如果氢数是【反应所必需】的（比如必须有两个 α-H 才能形成双键）→ 保留
    · 如果氢数只是【写 SMARTS 时脑子里那个例子】带来的 → 放宽
""")

F.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(f"规则总数 {len(data['rules'])}")
