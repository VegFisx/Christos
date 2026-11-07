# -*- coding: utf-8 -*-
r"""一次性探针：方剂里对不上的高频 token，**别名索引**里有没有？

若有，说明该做的是"把别名索引接进解析"，而不是去 Wikidata 找物种。
"""
from __future__ import annotations

import json
import sys

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

STAGE = r"D:\ProgramData\DSHNS\chemreact-staging"
sys.path.insert(0, STAGE + r"\sources")
import alias_index as AI                                   # noqa: E402

TOKENS = ["生地", "黄耆", "桂心", "官桂", "胆星", "炙草", "归尾", "龟版", "桑皮",
          "归身", "岗梅", "竹叶", "芒消", "豹骨", "制何首乌", "姜半夏", "清半夏",
          "硬脂酸镁", "糊精", "甘油", "桉油"]

print("别名索引里的样子（前 3 个候选）：")
for t in TOKENS:
    try:
        cs = AI.candidates(t)
    except Exception as ex:                                # noqa: BLE001
        cs = "ERR %s" % ex
    if isinstance(cs, list):
        print("  %-8s → %s" % (t, [(c.get("canonical"), c.get("source"))
                                    for c in cs[:3]] or "（无）"))
    else:
        print("  %-8s → %s" % (t, cs))
