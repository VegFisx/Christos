# -*- coding: utf-8 -*-
# 一次性探查：封杀 8 条"编辑型"模板的代价 —— 它们的 90 条"可用"切断出在多大的目标上？
# （R1 只在大目标 ≥12 重原子触发；若 90 条都在小目标上，"仅大目标封杀"可以零损失。）
import csv
import sys
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

STAGE = Path(r"D:\ProgramData\DSHNS\chemreact-staging")
for _p in (STAGE / "libs", STAGE / "tools", STAGE / "core"):
    if _p.is_dir() and str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from rdkit import Chem, RDLogger                       # noqa: E402
import retro_search as rs                              # noqa: E402

RDLogger.DisableLog("rdApp.*")

KEYS = ("usable_small", "usable_big", "R1_small", "R1_big", "R2_small", "R2_big",
        "R3_small", "R3_big", "run_fail")


def load_targets(n):
    seen, out = set(), []
    with open(STAGE / "reports" / "query_inventory_paths.csv",
              encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            smi = str(row.get("product_smiles") or "").strip()
            if not smi or smi in seen:
                continue
            m = Chem.MolFromSmiles(smi)
            if m is None:
                continue
            seen.add(smi)
            out.append(Chem.MolToSmiles(m))
            if len(out) >= n:
                break
    return out


DIRTY = [451, 452, 1208, 1041, 1042, 1161, 88, 954]
targets = load_targets(56)
tmpl = rs.load_rdchiral_templates()
sel = [(i, t) for i, t in enumerate(tmpl, 1) if i in DIRTY]
print("选到模板 %d 条（期望 8）· 目标 %d 个" % (len(sel), len(targets)))

tot = {k: 0 for k in KEYS}
for i, t in sel:
    c = {k: 0 for k in KEYS}
    for tgt in targets:
        hac = Chem.MolFromSmiles(tgt).GetNumHeavyAtoms()
        big = "big" if hac >= 12 else "small"
        try:
            outs = t.rxn.RunReactants((Chem.MolFromSmiles(tgt),))
        except Exception:
            c["run_fail"] += 1
            continue
        for tup in outs:
            prec = tuple(rs.canon(Chem.MolToSmiles(p)) for p in tup if p is not None)
            prec = tuple(p for p in prec if p)
            if not prec:
                continue
            ok, why = rs.step_usability(tgt, prec)
            if ok:
                c["usable_" + big] += 1
            elif why.startswith("R1"):
                c["R1_" + big] += 1
            elif why.startswith("R2"):
                c["R2_" + big] += 1
            elif why.startswith("R3"):
                c["R3_" + big] += 1
    for k in KEYS:
        tot[k] += c[k]
    print("idx %4d: 可用[小%2d 大%2d] R1[小%3d 大%4d] R2[小%2d 大%3d] R3[小%2d 大%2d]" % (
        i, c["usable_small"], c["usable_big"], c["R1_small"], c["R1_big"],
        c["R2_small"], c["R2_big"], c["R3_small"], c["R3_big"]))
print("=" * 74)
print("8 条合计: 可用[小 %d · 大 %d] · R1[小 %d · 大 %d] · R2[小 %d · 大 %d] · R3[小 %d · 大 %d]" % (
    tot["usable_small"], tot["usable_big"], tot["R1_small"], tot["R1_big"],
    tot["R2_small"], tot["R2_big"], tot["R3_small"], tot["R3_big"]))
print("-> 「仅大目标封杀」损失 = 可用大 %d 条；「全封杀」损失 = %d 条（大+小）"
      % (tot["usable_big"], tot["usable_big"] + tot["usable_small"]))
