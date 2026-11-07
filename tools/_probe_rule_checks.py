# -*- coding: utf-8 -*-
# 实测两个问题：
#  ① 3 条 no-op 逆模板（tid 529/1414/2358）套到 56 个目标上：会不会产出"目标==前体"的自切断？
#  ② dirty-8 的每条切断算"元素全覆盖比" max(Σ元素min / 目标重原子)，对照现有判定：
#     确定性规则"某前体含目标全部重原子元素计数 -> 残基路线"能覆盖多少、代价多少
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
by_tid = {t.tid: t for t in tmpl}

print("== ① no-op 模板（tid 529 硫酸 / 1414 磷酸 / 2358 甲基丙烯酸）套 56 目标 ==")
for tid in (529, 1414, 2358):
    t = by_tid.get(tid)
    if t is None:
        print("  tid %d 不在编译集" % tid)
        continue
    n_cut = n_self = 0
    ex = None
    for tgt in targets:
        try:
            outs = t.rxn.RunReactants((Chem.MolFromSmiles(tgt),))
        except Exception:
            continue
        for tup in outs:
            prec = tuple(rs.canon(Chem.MolToSmiles(p)) for p in tup if p is not None)
            prec = tuple(p for p in prec if p)
            if not prec:
                continue
            n_cut += 1
            if tgt in prec:
                n_self += 1
                ex = (tgt, prec)
    print("  tid %4d: 命中切断 %d 个 · 其中 目标==前体 %d 个 %s"
          % (tid, n_cut, n_self, ("e.g. " + ex[1][0][:60]) if ex else ""))

print()
print("== ② dirty-8：'元素全覆盖比' 与现有判定的对照 ==")
DIRTY = [451, 452, 1208, 1041, 1042, 1161, 88, 954]
by_idx = {i: t for i, t in enumerate(tmpl, 1)}
stat = {"usable": [0, 0, 0], "R1": [0, 0], "R2": 0}   # usable: [全部, ratio==1.0, 0.95<=r<1.0]
for i in DIRTY:
    t = by_idx.get(i)
    if t is None:
        continue
    for tgt in targets:
        t_hac = Chem.MolFromSmiles(tgt).GetNumHeavyAtoms()
        try:
            outs = t.rxn.RunReactants((Chem.MolFromSmiles(tgt),))
        except Exception:
            continue
        for tup in outs:
            prec = tuple(rs.canon(Chem.MolToSmiles(p)) for p in tup if p is not None)
            prec = tuple(p for p in prec if p)
            if not prec:
                continue
            r_max = 0.0
            for p in prec:
                ub = rs._common_atom_upper_bound(rs._elem_counts(tgt), rs._elem_counts(p))
                r_max = max(r_max, ub / max(1, t_hac))
            ok, why = rs.step_usability(tgt, prec)
            if ok:
                stat["usable"][0] += 1
                if r_max >= 0.999:
                    stat["usable"][1] += 1
                elif r_max >= 0.95:
                    stat["usable"][2] += 1
            elif why.startswith("R1"):
                stat["R1"][0] += 1
                if r_max >= 0.999:
                    stat["R1"][1] += 1
            elif why.startswith("R2"):
                stat["R2"] += 1
print("  现有可用 %d 条：其中元素全覆盖比==1.0 的 %d 条（确定性规则会收回）· "
      "0.95~1.0 的 %d 条" % (stat["usable"][0], stat["usable"][1], stat["usable"][2]))
print("  现有 R1 %d 条：其中元素全覆盖比==1.0 的 %d 条（= 可确定性复算）" % (stat["R1"][0], stat["R1"][1]))
print("  R2 %d 条（前体更大，不受此规则影响）" % stat["R2"])
