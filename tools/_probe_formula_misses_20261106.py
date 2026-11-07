# -*- coding: utf-8 -*-
"""两个未命中目标的定性：芍药苷 → 芍药苷元酮；野樱苷 → 苯甲醛。

只回答一个问题：产物里有没有目标分子式/结构，若有是被哪个规则给出的。
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
CASES = [
    ("Paeoniflorin", "HBIN038606", "C17H18O6"),   # 芍药苷元酮
    ("Prunasin", "HBIN040963", "C7H6O"),          # 苯甲醛
    ("Prunasin", "HBIN040963", "C8H7NO"),         # 扁桃腈
]


def main() -> int:
    con = sqlite3.connect(DB, uri=True)
    for name, iid, want_formula in CASES:
        row = con.execute("select name_en, smiles from compounds where ingredient_id=?",
                          (iid,)).fetchone()
        smi = row[1]
        spec = qb.RunSpec(seeds=[(name, smi, "probe")], cond_name="煎煮", rounds=1,
                          max_pairs=1, max_products_per_pair=64,
                          use_curated_templates=True, strict_redox_gate=True)
        inv = qb.build_inventory(spec, score=False, use_cache=False)
        hops = rp.expand_co_products(rp.hops_from_paths(inv.paths))
        hits = []
        for h in hops:
            try:
                m = Chem.MolFromSmiles(h.product)
                if m is None:
                    continue
                f = Chem.rdMolDescriptors.CalcMolFormula(m)
            except Exception:
                continue
            if f == want_formula:
                hits.append((h.rule, h.product, getattr(h, "alt_rules", "")))
        print(f"\n{name} → {want_formula}: {len(hops)} 跳，命中 {len(hits)} 条")
        for r, s, alt in hits[:6]:
            print(f"   rule={r} alt={alt or '-'} smi={s[:70]}")
        if not hits:
            # 打印产物分子式分布的前 8 个，看差在哪
            from collections import Counter
            c = Counter()
            for h in hops:
                try:
                    m = Chem.MolFromSmiles(h.product)
                    if m:
                        c[Chem.rdMolDescriptors.CalcMolFormula(m)] += 1
                except Exception:
                    pass
            print("   产物分子式前 8：", c.most_common(8))
    con.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
