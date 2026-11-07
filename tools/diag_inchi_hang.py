# -*- coding: utf-8 -*-
r"""把【RDKit InChI 会挂死】的分子揪出来（一次性诊断）。

背景：InChI 计算在个别分子上会死循环（CPU 100% 永不返回），
      第一次全量跑就卡死在"计算砌块 InChIKey 282,000/297,885"。
      现在用 30 秒/chunk 的线程池扫一遍，把挂死的列出来。
输出 reports\diag_inchi_hang.json

用法: python diag_inchi_hang.py
"""
import json
import sys
import time
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

STAGE = Path(r"D:\ProgramData\DSHNS\chemreact-staging")
sys.path.insert(0, str(STAGE / "tools"))
sys.path.insert(0, str(STAGE / "libs"))
sys.path.insert(0, r"D:\TCMAI\src")

from build_purchasable_blocks import (TSV_ALL, TSV_CORE, TSV_REAGENT,
                                       inchi_keys_with_timeout)
from rdkit import Chem, RDLogger
from rdkit.Chem import Descriptors

RDLogger.DisableLog("rdApp.*")
OUT = STAGE / "reports" / "diag_inchi_hang.json"


def load():
    out = []
    for p in (TSV_ALL,):
        with open(p, encoding="utf-8") as f:
            for line in f:
                if line.startswith("#") or line.startswith("smiles\t"):
                    continue
                c = line.rstrip("\n").split("\t")
                if len(c) == 9:
                    out.append(c[0])
    return out


def main():
    smis = sorted(set(load()))
    print(f"待查分子 {len(smis):,}", flush=True)
    t0 = time.time()
    got, hung = inchi_keys_with_timeout(smis, workers=10, chunk=300,
                                        chunk_timeout=30.0, label="[hang扫]")
    print(f"\n完成 {len(got):,}，挂死 {len(hung):,}，耗时 {time.time()-t0:.0f}s")
    recs = []
    for s in hung:
        m = Chem.MolFromSmiles(s)
        recs.append({
            "smiles": s,
            "formula": None if m is None else Chem.rdMolDescriptors.CalcMolFormula(m),
            "MW": None if m is None else round(Descriptors.MolWt(m), 2),
            "heavy_atoms": None if m is None else m.GetNumHeavyAtoms(),
            "n_radical_electrons": None if m is None else sum(a.GetNumRadicalElectrons() for a in m.GetAtoms()),
        })
    print("\n挂死分子一览:")
    for r in recs[:60]:
        print(f"   {str(r['formula']):<18} MW{str(r['MW']):>8}  "
              f"rad={r['n_radical_electrons']}  {r['smiles'][:70]}")
    OUT.write_text(json.dumps({"n_checked": len(smis), "n_hung": len(hung),
                               "records": recs}, ensure_ascii=False, indent=2),
                   encoding="utf-8")
    print(f"\n-> {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
