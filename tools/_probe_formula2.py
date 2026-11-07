# -*- coding: utf-8 -*-
"""一次性探针（只读）：方剂组成清洗（去剂量/标点/杂项）后，能对上 tcm.db 多少。"""
from __future__ import annotations

import json
import re
import sqlite3
import sys
from collections import Counter
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

FJ = Path(r"D:\TCMAI\data\formula_db.json")
TCM = r"D:\TCMAI\tcm.db"

DOSE = re.compile(r"\d+(?:\.\d+)?\s*(?:g|G|克|千克|kg|mg|毫克|钱|两|斤|ml|mL|毫升|升|L|"
                  r"片|粒|枚|条|个|只|对|支|瓶|袋|丸|滴|份|包)?")


def clean(tok: str) -> str:
    t = str(tok or "").strip()
    t = re.sub(r"[。．\.、；;：:，,（）()\[\]【】\s]+$", "", t)
    t = re.sub(r"^[（(【\[]+", "", t)
    t = DOSE.sub("", t).strip()
    t = re.sub(r"[。．\.、；;：:，,（）()\[\]【】\s]+$", "", t)
    return t


def main() -> None:
    d = json.loads(FJ.read_text(encoding="utf-8"))
    c = sqlite3.connect("file:" + TCM.replace("\\", "/") + "?mode=ro", uri=True)
    names = {r[0] for r in c.execute("SELECT name_cn FROM herbs")}
    PREP = ("生", "熟", "炙", "炒", "焦", "醋", "酒", "盐", "蜜", "姜", "制", "煅", "煨",
            "麸炒", "土炒", "米炒", "清炒", "酒炙", "蜜炙", "盐炙", "醋炙")
    stripped = {}
    for nm in names:
        for p in PREP:
            if nm.startswith(p) and len(nm) > len(p) + 1:
                stripped.setdefault(nm[len(p):], nm)
    c.close()

    raw_tot = raw_ok = cl_tot = cl_ok = cl_ok2 = 0
    miss = Counter()
    for v in d.values():
        for rec in v:
            pf = str(rec.get("peifang") or "")
            for tok in re.split(r"[，,、;；]", pf):
                tok = tok.strip()
                if not tok:
                    continue
                raw_tot += 1
                if tok in names:
                    raw_ok += 1
                t = clean(tok)
                if not t:
                    continue
                cl_tot += 1
                if t in names:
                    cl_ok += 1
                elif t in stripped:
                    cl_ok2 += 1
                else:
                    miss[t] += 1
    print("清洗前：%d 条，精确命中 %d（%.1f%%）"
          % (raw_tot, raw_ok, 100.0 * raw_ok / max(1, raw_tot)))
    print("清洗后：%d 条，精确命中 %d（%.1f%%）；去炮制前缀再命中 %d（累计 %.1f%%）"
          % (cl_tot, cl_ok, 100.0 * cl_ok / max(1, cl_tot), cl_ok2,
             100.0 * (cl_ok + cl_ok2) / max(1, cl_tot)))
    print()
    print("仍未命中 Top 30（看是不是化学药/辅料/异名）：")
    for t, n in miss.most_common(30):
        print("   %-14s %d" % (t, n))
    print()
    print("仍未命中总数（去重）= %d，占 token %d" % (len(miss), sum(miss.values())))


if __name__ == "__main__":
    main()
