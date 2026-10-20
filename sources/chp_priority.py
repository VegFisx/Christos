# -*- coding: utf-8 -*-
r"""药典优先排序（Tier-0 = 药典"含量测定/鉴别"成分）——**开关默认关**，打开才生效。

数据：**2026-10-15 起优先用 2025 版** reports/chp_markers_2025/chp2025_linked.csv
（用户拍板切换；旧 2020 版 reports/chp_markers/chp2020_linked.csv 留档回退）。
两版都由 build→curate→link 三脚本产出，行带出处（2025 版含官方条目 URL）。
口径：Tier-0（含量测定，含总量类）> Tier-1（鉴别对照品）> 其余（保持原序）。
同 Tier 内按**限量值从大到小**（药典原文数字，非我们打分）；ID 缺失的行不参与排序。
"""
from __future__ import annotations

import csv
import re
from pathlib import Path

_OLD = Path(r"D:\ProgramData\DSHNS\chemreact-staging\reports\chp_markers\chp2020_linked.csv")
_NEW = Path(r"D:\ProgramData\DSHNS\chemreact-staging\reports\chp_markers_2025\chp2025_linked.csv")
CSV = _NEW if _NEW.exists() else _OLD     # 2026-10-15：用户拍板切换 2025 版；旧版文件留档


def load_map():
    """{herb: {ingredient_id: (tier, value, part, name)}}；缺失文件时返回空（不报错）。"""
    data = {}
    if not CSV.exists():
        return data
    with open(CSV, encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            if r.get("entry_type") == "制剂":      # 成方制剂不参与药材优先序
                continue
            if r.get("kind") == "aggregate":
                continue
            tier = 0 if r.get("kind") in ("compound", "aggregate_total") else 1
            try:
                val = float(r.get("value") or 0)
            except ValueError:
                val = 0.0
            for i in re.findall(r"\((HBIN\d+)\)", r.get("db_hits", "")):
                cur = data.setdefault(r["herb"], {})
                old = cur.get(i)
                if old is None or val > old[1]:
                    cur[i] = (tier, val, r.get("part", ""), r.get("name", ""))
    return data
