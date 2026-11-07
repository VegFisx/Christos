# -*- coding: utf-8 -*-
r"""建 COCONUT 参照库缓存：272,992 个化合物 -> InChIKey 索引。

用途：把预测产物回查【已知天然产物】，判断"预测出来的分子是不是真实存在的东西"。
COCONUT 没有 inchi 列，所以要自己从 SMILES 算。

输出 JSONL（每行）：inchi_key <TAB> name <TAB> np_likeness <TAB> chemical_class
缓存后可重复使用，不必重算。

用法: python build_coconut_index.py
"""
import json
import sqlite3
import sys
import time
from pathlib import Path

STAGE = Path(r"D:\ProgramData\DSHNS\chemreact-staging")
sys.path.insert(0, str(STAGE / "libs"))

from rdkit import Chem, RDLogger  # noqa: E402

RDLogger.DisableLog("rdApp.*")

COCO = Path(r"D:\TCMAI\coconut.db")
OUT = STAGE / "reports" / "coconut_inchikey_index.jsonl"
OUT.parent.mkdir(parents=True, exist_ok=True)

t0 = time.time()
con = sqlite3.connect(f"file:{COCO}?mode=ro", uri=True)
cur = con.cursor()
cur.execute("""SELECT cnp_id, name, smiles, np_likeness, chemical_class
               FROM compounds
               WHERE smiles IS NOT NULL AND smiles != '' AND smiles != 'None'""")
rows = cur.fetchall()
con.close()
print(f"COCONUT 可用化合物 {len(rows):,} 条，读取耗时 {time.time()-t0:.1f}s", flush=True)

n_ok = n_bad = 0
seen = set()
t0 = time.time()
with open(OUT, "w", encoding="utf-8") as f:
    for i, (cnp, name, smi, npl, cls) in enumerate(rows):
        m = Chem.MolFromSmiles(smi)
        if m is None:
            n_bad += 1
            continue
        try:
            ik = Chem.MolToInchiKey(m)
        except Exception:
            n_bad += 1
            continue
        if not ik:
            n_bad += 1
            continue
        if ik in seen:
            continue
        seen.add(ik)
        n_ok += 1
        nm = (name or "").replace("\t", " ").replace("\n", " ")
        cl = (cls or "").replace("\t", " ").replace("\n", " ")
        f.write(f"{ik}\t{nm}\t{'' if npl is None else round(float(npl), 3)}\t{cl}\n")
        if (i + 1) % 50000 == 0:
            el = time.time() - t0
            print(f"   {i+1:,}/{len(rows):,}  已索引 {n_ok:,}  "
                  f"耗时 {el/60:.1f} 分钟  预计还需 "
                  f"{el/(i+1)*(len(rows)-i-1)/60:.1f} 分钟", flush=True)

dt = time.time() - t0
print(f"\n完成：唯一 InChIKey {n_ok:,} 个，无法解析 {n_bad:,} 个，"
      f"耗时 {dt/60:.1f} 分钟")
print(f"输出: {OUT}  ({OUT.stat().st_size/1024**2:.1f} MB)")

# 自检：随机抽 3 行看格式
with open(OUT, encoding="utf-8") as f:
    for i, line in enumerate(f):
        if i >= 3:
            break
        print("   " + line.rstrip()[:150])
