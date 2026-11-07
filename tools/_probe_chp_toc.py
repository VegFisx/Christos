# -*- coding: utf-8 -*-
"""一次性探针（只读）：药典目录里有多少"成方制剂"名字，和方剂库比缺多少。"""
from __future__ import annotations

import csv
import json
import re
import sys
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

TOC = Path(r"D:\ProgramData\DSHNS\chemreact-staging\reports\_probe_net\chp2025_toc.csv")
FJ = Path(r"D:\TCMAI\data\formula_db.json")


def norm(s: str) -> str:
    t = re.sub(r"\s+", "", str(s or ""))
    t = re.sub(r"[（(].*?[)）]", "", t)          # 去掉剂型后缀，如（浓缩丸）
    return t


def main() -> None:
    rows = list(csv.DictReader(TOC.open(encoding="utf-8")))
    print("目录行 =", len(rows))
    parts = {}
    for r in rows:
        parts[r["部号"]] = parts.get(r["部号"], 0) + 1
    print("部号分布：", parts)
    print("样例 10 行：")
    for r in rows[:10]:
        print("   ", r)
    # 找"成方制剂"所在的分节标记
    marks = [r for r in rows if any(k in r["目录"] for k in ("成方制剂", "单味制剂", "目录"))]
    print("分节标记样例：")
    for r in marks[:12]:
        print("   ", r)
    # 名字总集合
    one = [r for r in rows if "一部" in str(r["部号"] or "")]
    print("\n一部条目 =", len(one))
    # 切出"成方制剂"段：一部的目录按 药材 → 成方制剂 顺序，用页号分界最稳。
    # 先看页号分布，找断层。
    def pnum(x):
        try:
            return int(str(x).strip())
        except ValueError:
            return -1
    ps = sorted(pnum(r["页号"]) for r in one if pnum(r["页号"]) > 0)
    print("一部页号范围：%d ~ %d" % (ps[0], ps[-1]))
    # 打印页号递增过程中的大跳变（可能的分节边界）
    jumps = [(ps[i], ps[i + 1]) for i in range(len(ps) - 1) if ps[i + 1] - ps[i] > 3]
    print("页号跳变（可能的分节）：", jumps[:12])
    # 成方制剂一般在一部后半。试几种切法，看哪种切出来的名字与方剂库交集最高
    d0 = json.loads(FJ.read_text(encoding="utf-8"))
    fnames0 = {norm(k) for k in d0}
    best = None
    for cut in sorted({p for _a, p in jumps}):
        seg = {norm(r["目录"]) for r in one if pnum(r["页号"]) >= cut}
        seg = {n for n in seg if n}
        if not seg:
            continue
        hit = len(seg & fnames0)
        print("   切在 p%-5d 段内 %4d 条，与方剂库交集 %4d（%.0f%%）"
              % (cut, len(seg), hit, 100.0 * hit / len(seg)))
        if best is None or hit > best[1]:
            best = (cut, hit, seg)
    if best is None:
        return
    cut, _hit, names = best
    print("\n采用切点 p%d：一部成方制剂段名字 = %d" % (cut, len(names)))
    d = json.loads(FJ.read_text(encoding="utf-8"))
    fnames = {norm(k) for k in d}
    inter = names & fnames
    print("与方剂库交集 =", len(inter))
    miss = sorted(names - fnames)
    print("药典有、方剂库没有 = %d，样例：" % len(miss))
    for x in miss[:40]:
        print("   ", x)


if __name__ == "__main__":
    main()
