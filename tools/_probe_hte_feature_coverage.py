# -*- coding: utf-8 -*-
r"""一次性探针：HTE 训练表的【特征取值覆盖】——判断查询路径的条件能不能喂进模型。

问题：模型把 solvent/catalyst/base 当类别 one-hot 训练。
若查询侧的条件取值（如 water / 无催化剂 / 无碱）在训练表里根本不存在，
那就是**分布外输入**，模型分数没有意义。本脚本只回答这一个问题。
"""
import csv
import sys
from collections import Counter
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

CSV = (Path(r"D:\ProgramData\DSHNS\chemreact-staging") / "data" / "external" / "bh-hte-ood"
       / "schwallergroup-bh-hte-ood-a277041" / "data" / "BH_HTE_Curated_Dataset_v20260219.csv")

cnt = {k: Counter() for k in ("Solvent Name", "Catalyst Name", "Base Name", "Source")}
blank = Counter()
n = 0
with open(CSV, encoding="utf-8", newline="") as f:
    for row in csv.DictReader(f):
        n += 1
        for k in cnt:
            v = str(row.get(k) or "").strip()
            if not v:
                blank[k] += 1
            cnt[k][v] += 1

print("总行数 %d" % n)
for k in cnt:
    print("")
    print("== %s ==  空值 %d 行；取值 %d 种" % (k, blank[k], len(cnt[k])))
    for v, c in cnt[k].most_common(10 if k != "Solvent Name" else 18):
        print("   %6d  %s" % (c, v if v else "(空字符串)"))
    for probe in ("empty", "(空)", "None"):
        if probe in cnt[k]:
            print("   [空值类] %s -> %d 行" % (probe, cnt[k][probe]))
    for probe in ("water", "Water", "H2O", "DMSO", "toluene"):
        if probe in cnt[k]:
            print("   [命中] %s -> %d 行" % (probe, cnt[k][probe]))
