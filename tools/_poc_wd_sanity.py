# -*- coding: utf-8 -*-
r"""一次性对照：用**常见**药材名跑同一条 Wikidata 链路（证信道本身是通的）。"""
from __future__ import annotations

import sys
import time

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

sys.path.insert(0, r"D:\ProgramData\DSHNS\chemreact-staging\tools")
from _poc_alias_species_wikidata import (wd_search, wd_entity, scientific_name,
                                         is_taxon, name_matches)   # noqa: E402

for nm in ("甘草", "黄连", "丹参", "银杏", "龙胆"):
    try:
        hits = wd_search(nm)
        found = ""
        for h in hits[:3]:
            ent = wd_entity(h["id"])
            if is_taxon(ent) and name_matches(nm, ent):
                found = "%s [%s] %s" % (h.get("label", ""), h["id"], scientific_name(ent))
                break
        print("  %-4s → %s" % (nm, found or "（前 3 个候选都不是分类单元）"))
    except Exception as ex:                                # noqa: BLE001
        print("  %-4s ★ %s: %s" % (nm, type(ex).__name__, ex))
    time.sleep(1.0)
