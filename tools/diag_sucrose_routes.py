# -*- coding: utf-8 -*-
"""诊断蔗糖为何 0 条完整路线（只读，不改任何库）。

打印：目标/糖的 InChIKey 与终止集合命中情况、深度 1 的切断方案、
按“前体可得数”排序的前 25 个方案。
"""
from __future__ import annotations

import sys
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

STAGE = Path(__file__).resolve().parent.parent
for sub in ("core", "rules", "libs", "tools", "sources", "conditions"):
    p = STAGE / sub
    if p.is_dir() and str(p) not in sys.path:
        sys.path.insert(0, str(p))

from rdkit import Chem, RDLogger  # noqa: E402

RDLogger.DisableLog("rdApp.*")
import retro_search as rs  # noqa: E402

TARGET = ("OC[C@H]1O[C@@](CO)(O[C@H]2O[C@H](CO)[C@@H](O)[C@H](O)"
          "[C@H]2O)[C@@H](O)[C@@H]1O")


def ik(smi: str) -> str:
    m = Chem.MolFromSmiles(smi)
    return Chem.MolToInchiKey(m) if m is not None else ""


def hac(smi: str) -> int:
    m = Chem.MolFromSmiles(smi)
    return m.GetNumHeavyAtoms() if m is not None else -1


def main() -> int:
    templates = rs.load_rdchiral_templates()
    av = rs.load_available()
    bf, bs = rs.load_purchasable_blocks()
    eng = rs.RetroSearch(templates, av, blocks_full=bf, blocks_skel=bs)

    print("target canonical:", Chem.MolToSmiles(Chem.MolFromSmiles(TARGET)))
    print("target HAC:", hac(TARGET), "IK:", ik(TARGET),
          "available:", eng.is_available(TARGET))
    print("templates:", len(templates), "available keys:", len(av),
          "blocks:", len(bf), len(bs))

    sugars = {
        "alpha-D-glucose": "OC[C@H]1O[C@H](O)[C@@H](O)[C@H](O)[C@H]1O",
        "beta-D-glucose": "OC[C@H]1O[C@@H](O)[C@H](O)[C@@H](O)[C@@H]1O",
        "alpha-D-fructofuranose": "OC[C@H]1O[C@](O)(CO)[C@H](O)[C@H]1O",
        "beta-D-fructofuranose": "OC[C@H]1O[C@](O)(CO)[C@@H](O)[C@@H]1O",
        "D-glucose-open": "O=C[C@H](O)[C@@H](O)[C@H](O)[C@H](O)CO",
        "D-fructose-open": "O=C(CO)[C@@H](O)[C@H](O)[C@H](O)CO",
    }
    print("\n-- sugar availability --")
    for name, smi in sugars.items():
        k = ik(smi)
        print("%-24s HAC=%2d IK=%s avail=%s src=%s"
              % (name, hac(smi), k, eng.is_available(smi), av.get(k, "")))

    dis = eng.disconnections(TARGET)
    print("\ndepth1 disconnections:", len(dis))
    rows = []
    for st in dis:
        avs = [bool(eng.is_available(p)) for p in st.precursors]
        rows.append((sum(avs), len(st.precursors), st, avs))
    rows.sort(key=lambda x: (-x[0], x[1], -max(hac(p) for p in x[2].precursors)))
    print("\n-- top disconnections by available-precursor count --")
    for n_av, n, st, avs in rows[:25]:
        print("[%d/%d available]" % (n_av, n))
        for p, a in zip(st.precursors, avs):
            print("   %s HAC=%2d %s" % ("AV" if a else "--", hac(p), p))
        print("   tmpl:", st.template[:170])

    print("\n-- disconnections with two sugar-sized (HAC 10-14) precursors --")
    n_sugar = 0
    for st in dis:
        hs = [hac(p) for p in st.precursors]
        if len(st.precursors) == 2 and all(10 <= h <= 14 for h in hs):
            n_sugar += 1
            avs = [bool(eng.is_available(p)) for p in st.precursors]
            print("HAC=%s avail=%s" % (hs, avs))
            for p, a in zip(st.precursors, avs):
                print("   %s %s" % ("AV" if a else "--", p))
            print("   tmpl:", st.template[:170])
    print("sugar_sugar_steps=", n_sugar)

    from collections import Counter
    hist = Counter((len(st.precursors), tuple(sorted(hac(p) for p in st.precursors)))
                   for st in dis)
    print("\n-- precursor-count/HAC histogram (top 15) --")
    for k, n in hist.most_common(15):
        print(k, n)
    return 0


if __name__ == "__main__":
    sys.exit(main())
