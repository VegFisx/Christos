# -*- coding: utf-8 -*-
"""一次性探针（只读）：拉丁名路由矩阵。

规则（用户 2026-10-15 明确）：
  1 含药典部位词（Radix/Rhizoma/Folium/Herba/Cortex/Fructus/Semen/Flos…）
    -> 药材拉丁名 -> HERB
  2 命中 COCONUT 种名字典 -> 物种拉丁名 -> COCONUT
  3 其余（中文名等）-> HERB
判据**不是**"有没有拉丁字母"。
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

STAGE = Path(r"D:\ProgramData\DSHNS\chemreact-staging")
for _p in (STAGE / "sources", STAGE / "core"):
    sys.path.insert(0, str(_p))

import coconut as CC                 # noqa: E402
from herb import compounds_of_herb   # noqa: E402

CASES = [
    ("甘草", "HERB"),
    ("白鲜皮", "HERB"),
    ("Radix et Rhizoma Glycyrrhizae", "HERB"),
    ("Ginkgo Folium", "HERB"),
    ("Cortex Dictamni", "HERB"),
    ("Radix Glycyrrhizae Uralensis", "HERB"),
    ("Glycyrrhiza uralensis", "COCONUT"),
    ("Glycirrhiza uralensys", "COCONUT"),
    ("Dictamnus dasycarpus", "COCONUT"),
    ("Ginkgo biloba", "COCONUT"),
    ("Coffea arabica", "COCONUT"),
    ("gancao", "NONE"),
    ("glycyrrhiza", "GENUS"),
    ("panax", "GENUS"),
    ("ginkgo", "GENUS"),
]


def route_of(h):
    """返回 (走哪条路, 依据, 种名) —— 与桥接层的 auto 判定保持同一套判据。"""
    if re.search(r"[A-Za-z]", h):
        part = CC.looks_like_drug_latin(h)
        if part:
            return "herb", "药材拉丁名(部位词 %s)" % part, None
        sp, how = CC.looks_like_species(h)
        if sp:
            return "coconut", "%s -> %s" % (how, sp), sp
        g = CC.genus_species(h)
        if g:
            return "genus", "属名：%d 个物种待选" % len(g), None
    return "herb", "非拉丁 / 无种名", None


def main():
    bad = 0
    print("%-3s %-32s %-9s %-9s %7s  %s"
          % ("", "输入", "实际", "期望", "成分数", "依据"))
    print("-" * 104)
    for h, want in CASES:
        src, how, sp = route_of(h)
        if src == "coconut":
            n = len(CC.compounds_of_species(sp))
            got = "COCONUT"
        elif src == "genus":
            n = len(CC.genus_species(h))
            got = "GENUS"
        else:
            n = len(compounds_of_herb(h, limit=10 ** 7))
            got = "HERB" if n else "NONE"
        flag = "OK" if got == want else "!!"
        if got != want:
            bad += 1
        print("%-3s %-32s %-9s %-9s %7d  %s" % (flag, h, got, want, n, how))
    print("-" * 104)
    print("不符期望：%d 个" % bad)
    return 0 if bad == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
