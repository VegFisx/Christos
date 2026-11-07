# -*- coding: utf-8 -*-
# 一次性探查：8 条"编辑型"模板里判为"可用"的样例到底长什么样（真有用 or R1 漏判）
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


targets = load_targets(56)
tmpl = rs.load_rdchiral_templates()
by_idx = {i: t for i, t in enumerate(tmpl, 1)}

for i, want in ((451, 3), (1161, 2), (88, 2)):
    t = by_idx.get(i)
    shown = 0
    for tgt in targets:
        if shown >= want:
            break
        hac = Chem.MolFromSmiles(tgt).GetNumHeavyAtoms()
        for tup in t.rxn.RunReactants((Chem.MolFromSmiles(tgt),)):
            prec = tuple(rs.canon(Chem.MolToSmiles(p)) for p in tup if p is not None)
            prec = tuple(p for p in prec if p)
            if not prec:
                continue
            ok, why = rs.step_usability(tgt, prec)
            if ok:
                shown += 1
                ov = rs._common_atom_upper_bound(rs._elem_counts(tgt),
                                                 rs._elem_counts(prec[0]))
                print("idx %d [可用] 目标重原子 %d 重叠上界比 %.2f" % (i, hac, ov / hac))
                print("   目标 %s" % tgt[:78])
                for p in prec:
                    print("   前体 %s" % p[:78])
                break
print("（以上为上界比例 <0.8 或 MCS 未达阈值才可能判可用）")
