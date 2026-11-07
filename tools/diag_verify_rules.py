# -*- coding: utf-8 -*-
"""诊断 3 条 verify 规则：查清是引擎能力边界，还是 SMARTS 写错。

重点先验证一个基础问题：SMARTS 里 X（连接数）到底怎么算？
  肉桂酸 Ar-CH=CH-COOH 的 α 碳有 2 个重原子邻居 + 1 个 H，
  它该写成 [CX2H] 还是 [CX3H]？
  这个基础问题搞错，后面全是错的。
"""
import sys
from pathlib import Path

STAGE = Path(r"D:\ProgramData\DSHNS\chemreact-staging")
for d in ("rules", "libs"):
    p = STAGE / d
    if p.is_dir():
        sys.path.insert(0, str(p))

from rdkit import Chem
from rdkit.Chem import AllChem

print("=" * 88)
print("① 基础：SMARTS 的 X / D / H 在肉桂酸上到底是什么")
print("=" * 88)
CINNAMIC = "OC(=O)/C=C/c1ccccc1"
m = Chem.MolFromSmiles(CINNAMIC)
print(f"肉桂酸: {CINNAMIC}")
for a in m.GetAtoms():
    if a.GetSymbol() != "C":
        continue
    print(f"  原子idx {a.GetIdx():>2} {a.GetSymbol()}  "
          f"重原子邻居={a.GetDegree()}  含H总连接={a.GetTotalDegree()}  "
          f"显式H={a.GetTotalNumHs()}  芳香={a.GetIsAromatic()}")

print()
print("各写法能否匹配到羧基旁边的那个 CH：")
for pat in ["[CX3H]", "[CX2H]", "[CH]", "[CX2H1]", "[CX3H1]", "[cX3H]", "[CX3]"]:
    q = Chem.MolFromSmarts(pat)
    ok = m.HasSubstructMatch(q) if q else None
    print(f"  {pat:<10} {'匹配' if ok else '不匹配'}")

print()
print("=" * 88)
print("② 三条 verify 规则：rdkit vs rdchiral，手工底物")
print("=" * 88)

CASES = {
    "cyclization_hemiacetal_001": [
        ("4-羟基丁醛", "O=CCCCO"),
        ("5-羟基戊醛", "O=CCCCCO"),
    ],
    "cyclization_lactam_001": [
        ("4-氨基丁酸", "NCCCC(=O)O"),
        ("5-氨基戊酸", "NCCCCC(=O)O"),
    ],
    "decarboxylation_cinnamic_001": [
        ("肉桂酸", "OC(=O)/C=C/c1ccccc1"),
        ("咖啡酸", "OC(=O)/C=C/c1ccc(O)c(O)c1"),
        ("阿魏酸", "OC(=O)/C=C/c1ccc(O)c(OC)c1"),
    ],
}

import json
rules = {r["id"]: r for r in json.loads(
    (STAGE / "rules" / "rules.json").read_text(encoding="utf-8"))["rules"]}

from rdchiral.main import rdchiralRun, rdchiralReaction, rdchiralReactants

for rid, probes in CASES.items():
    r = rules.get(rid)
    if r is None:
        continue
    print(f"\n【{r['name']}】{rid}")
    print(f"  SMARTS: {r['smarts']}")
    try:
        rxn_rd = AllChem.ReactionFromSmarts(r["smarts"])
        print(f"  rdkit 编译: OK（{rxn_rd.GetNumReactantTemplates()} 反应物 / "
              f"{rxn_rd.GetNumProductTemplates()} 产物）")
    except Exception as e:
        print(f"  rdkit 编译: ✗ {e}")
        continue
    try:
        rxn_rch = rdchiralReaction(r["smarts"])
        print(f"  rdchiral 接受: OK")
    except Exception as e:
        print(f"  rdchiral 拒绝: ✗ {str(e)[:80]}")
        rxn_rch = None

    for name, smi in probes:
        mol = Chem.MolFromSmiles(smi)
        # rdkit
        try:
            res = rxn_rd.RunReactants((mol,))
            n_rd = len(res)
            ex_rd = ""
            if res:
                frags = []
                for p in res[0]:
                    pc = Chem.Mol(p)
                    try:
                        Chem.SanitizeMol(pc)
                        frags.append(Chem.MolToSmiles(pc))
                    except Exception:
                        frags.append("(价态非法)")
                ex_rd = " → " + " + ".join(frags)
        except Exception as e:
            n_rd, ex_rd = -1, f" 异常 {str(e)[:40]}"
        # rdchiral
        n_rch, ex_rch = 0, ""
        if rxn_rch is not None:
            try:
                outs = rdchiralRun(rxn_rch, rdchiralReactants(smi)) or []
                n_rch = len(outs)
                if outs:
                    ex_rch = " → " + outs[0][:50]
            except Exception as e:
                n_rch, ex_rch = -1, f" 异常 {str(e)[:40]}"
        print(f"    {name:<12} rdkit={n_rd:<3}{ex_rd}")
        print(f"    {'':<12} rdchiral={n_rch:<3}{ex_rch}")
