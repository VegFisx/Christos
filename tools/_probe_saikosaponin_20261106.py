# -*- coding: utf-8 -*-
"""柴胡皂苷 → 柴胡皂苷元：种子是否挂到柴胡？单跑能不能出 C30H48O4？

只回答两个问题：(1) 柴胡的成分表里有没有 Saikosaponin a/d；(2) 直接拿库里的结构单跑，
产物里有没有柴胡皂苷元（按 InChIKey 前 14 位或分子式 C30H48O4）。
"""
from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
for _p in (_ROOT, _ROOT / "core", _ROOT / "conditions", _ROOT / "tools"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import query_base as qb            # noqa: E402
import reaction_paths as rp        # noqa: E402
import validate_literature_conversions as V   # noqa: E402
from rdkit import Chem             # noqa: E402

DB = "file:D:/TCMAI/tcm.db?mode=ro"
HERB = "HERB000638"   # 柴胡
SEEDS = [("Saikosaponin a", "HBIN042787"), ("Saikosaponin d", "HBIN042801")]
TARGETS = {"saikogenin_d": "HBIN042776", "saikogenin_f": "HBIN042778"}


def main() -> int:
    con = sqlite3.connect(DB, uri=True)
    linked = {r[0] for r in con.execute(
        "select ingredient_id from herb_compound where herb_id=?", (HERB,)).fetchall()}
    for nm, iid in SEEDS:
        print(f"- {nm} {iid} 挂到柴胡？ {'是' if iid in linked else '否'}")

    for nm, iid in SEEDS:
        row = con.execute("select smiles, name_en from compounds where ingredient_id=?",
                          (iid,)).fetchone()
        smi = row[0]
        spec = qb.RunSpec(seeds=[(row[1], smi, "柴胡")], cond_name="煎煮", rounds=1,
                          max_pairs=1, max_products_per_pair=64,
                          use_curated_templates=True, strict_redox_gate=True)
        inv = qb.build_inventory(spec, score=False, use_cache=False)
        hops = rp.expand_co_products(rp.hops_from_paths(inv.paths))
        print(f"\n{nm} 单跑：{len(hops)} 跳")
        for label, tid in TARGETS.items():
            trow = con.execute("select smiles from compounds where ingredient_id=?",
                               (tid,)).fetchone()
            want = V.full_inchikey(trow[0])[:14].upper()
            hit = [h for h in hops if V.full_inchikey(h.product)[:14].upper() == want]
            print(f"   {label}: {'命中 ' + str(len(hit)) + ' 条 rule=' + hit[0].rule if hit else '未命中'}")
        # 有没有任何 C30H48O4
        forms = []
        for h in hops:
            try:
                m = Chem.MolFromSmiles(h.product)
                if m and Chem.rdMolDescriptors.CalcMolFormula(m) == "C30H48O4":
                    forms.append((h.rule, h.product))
            except Exception:
                continue
        print(f"   C30H48O4 产物：{len(forms)} 条 {[r for r, _ in forms[:5]]}")
    con.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
