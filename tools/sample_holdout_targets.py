# -*- coding: utf-8 -*-
r"""第四十三轮：从 COCONUT 抽一批【留出目标】—— 验证黑名单泛化（不吃自家 56 个目标）。

口径（写死）：
  * 来源：D:\TCMAI\coconut.db（只读，走 tools\tcm_ro.py 的只读连接）
  * 过滤：重原子 15~70；规范化去重；剔除与现有 56 个目标重复的分子
  * 抽样：固定种子 SEED（可复现），按规范化 SMILES 排序后抽样 N 个
  * 输出：reports/_holdout_targets_coconut.txt（"smiles<TAB>name"，首行 # 注释带口径）

用法: python tools/sample_holdout_targets.py
"""
from __future__ import annotations

import csv
import random
import sys
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

STAGE = Path(r"D:\ProgramData\DSHNS\chemreact-staging")
for _p in (STAGE / "libs", STAGE / "tools"):
    if _p.is_dir() and str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from rdkit import Chem, RDLogger                       # noqa: E402
from tcm_ro import open_db, COCONUT_DB                 # noqa: E402

RDLogger.DisableLog("rdApp.*")

N = 64
SEED = 20261014
HAC_MIN, HAC_MAX = 15, 70
OUT = STAGE / "reports" / "_holdout_targets_coconut.txt"
CSV = STAGE / "reports" / "query_inventory_paths.csv"


def main() -> int:
    orig = set()
    if CSV.exists():
        with open(CSV, encoding="utf-8-sig", newline="") as f:
            for row in csv.DictReader(f):
                smi = str(row.get("product_smiles") or "").strip()
                m = Chem.MolFromSmiles(smi) if smi else None
                if m is not None:
                    orig.add(Chem.MolToSmiles(m))
    print("现有目标（要剔除的）：%d 个" % len(orig))

    pool = {}
    n_all = n_bad = 0
    with open_db(COCONUT_DB) as con:
        rows = con.execute(
            "SELECT smiles, name FROM compounds "
            "WHERE smiles IS NOT NULL AND smiles != '' AND smiles != 'None'").fetchall()
    print("COCONUT 可读分子：%d 条" % len(rows))
    for smi, name in rows:
        n_all += 1
        m = Chem.MolFromSmiles(str(smi))
        if m is None:
            n_bad += 1
            continue
        hac = m.GetNumHeavyAtoms()
        if not (HAC_MIN <= hac <= HAC_MAX):
            continue
        c = Chem.MolToSmiles(m)
        if c in orig or c in pool:
            continue
        pool[c] = (str(name or ""), hac)
    print("解析失败 %d · 落在重原子 %d~%d 且未去重前可用的 %d 个"
          % (n_bad, HAC_MIN, HAC_MAX, len(pool)), flush=True)

    keys = sorted(pool)
    rng = random.Random(SEED)
    sample = rng.sample(keys, min(N, len(keys)))
    sample.sort()
    hs = [pool[k][1] for k in sample]
    with open(OUT, "w", encoding="utf-8") as f:
        f.write("# COCONUT 留出目标 · seed=%d · N=%d · 重原子 %d~%d · 剔除与原 56 目标重复\n"
                % (SEED, len(sample), HAC_MIN, HAC_MAX))
        f.write("# 生成: tools/sample_holdout_targets.py（2026-10-14）\n")
        for k in sample:
            name, _ = pool[k]
            f.write("%s\t%s\n" % (k, name.replace("\t", " ")[:60]))
    print("抽样 %d 个（重原子 %d~%d，中位 %d）" % (len(sample), min(hs), max(hs),
                                                sorted(hs)[len(hs) // 2]))
    print("写出：%s" % OUT)
    return 0


if __name__ == "__main__":
    sys.exit(main())
