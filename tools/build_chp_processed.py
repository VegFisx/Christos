# -*- coding: utf-8 -*-
r"""从药典名录里挑出**炮制品**，做成"禁止替换成基原"的清单。

用户 2026-10-16 指出：`制何首乌` / `姜半夏` / `大蓟炭` 这些在药典里是**独立药材**
（各自有条目、各自有成分），**不能**因为"库里有基原"就替换成 何首乌/半夏/大蓟。

判据（数据驱动，不靠猜前缀）：一个药典收载的药材名，若
  ① 带炮制标记（前缀 制/炙/炒/焦/煅/煨/蒸/醋/酒/盐/蜜/姜/清/麸/土/米… 或后缀 炭/霜/曲），且
  ② 去掉标记后**仍是另一个药典收载药材**（= 它有明确的基原）
→ 判为炮制品，登记 `{name, base, marker}`。

输出 ``data/chp_processed.json``：``{"names":[...], "map":{炮制品: {base, marker}}}``
"""
from __future__ import annotations

import json
import re
import sys
import zipfile
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

STAGE = Path(r"D:\ProgramData\DSHNS\chemreact-staging")
sys.path.insert(0, str(STAGE / "sources"))      # ★ 少这一行会让下面的 import 静默失败
Z = STAGE / "reports" / "_probe_net" / "indkb.zip"
SUB = "一部/药材和饮片/"
OUT = STAGE / "data" / "chp_processed.json"

HEAD = ("制", "炙", "炒", "焦", "煅", "煨", "蒸", "煮", "醋", "酒", "盐", "蜜", "姜",
        "清", "麸", "土", "米", "朱砂", "滑石", "蛤粉", "甘草水", "酒蒸", "酒炙",
        "蜜炙", "盐炙", "醋炙", "麸炒", "土炒", "米炒", "清炒", "炒炭", "炒焦")
TAIL = ("炭", "霜", "曲")


def main() -> int:
    z = zipfile.ZipFile(Z)
    names = sorted({Path(i.filename).stem for i in z.infolist()
                    if i.filename.endswith(".md") and SUB in i.filename})
    nameset = set(names)
    print("药典收载药材 = %d" % len(names))
    mp = {}
    # ★ 第二道判据（防假阳性）：炮制品必须与基原**同物种**。
    #   实测踩到「土木香→木香」「土茯苓→茯苓」——名字里那个"土"不是炮制标记，
    #   土木香是 Inula helenium、木香是 Aucklandia lappa，两种植物。
    try:
        import herb_species as HS
    except Exception as ex:                                  # noqa: BLE001 —— 打印，不静默
        print("   [warn] 物种判据不可用（%s: %s）——**假阳性不会被剔除**，结果不可信"
              % (type(ex).__name__, ex))
        HS = None
    dropped = []
    for nm in names:
        base = marker = ""
        for h in sorted(HEAD, key=len, reverse=True):
            if nm.startswith(h) and len(nm) > len(h) + 1 and nm[len(h):] in nameset:
                base, marker = nm[len(h):], h
                break
        if not base:
            for t in TAIL:
                if nm.endswith(t) and len(nm) > len(t) + 1 and nm[:-len(t)] in nameset:
                    base, marker = nm[:-len(t)], t
                    break
        if base:
            if HS is not None:
                sa, sb = set(HS.species_of(nm)), set(HS.species_of(base))
                if sa and sb and not (sa & sb):
                    dropped.append((nm, base, sorted(sa)[:1], sorted(sb)[:1]))
                    continue
            mp[nm] = {"base": base, "marker": marker}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({"names": sorted(mp), "map": mp},
                              ensure_ascii=False, indent=1), encoding="utf-8")
    print("判为炮制品 = %d（其中带基原的）" % len(mp))
    if dropped:
        print("★ 被物种判据剔除的 %d 个（名字像炮制、其实不是同一物种）：" % len(dropped))
        for d in dropped:
            print("   %-8s ✗ 基原 %-8s  物种 %s vs %s" % (d[0], d[1], d[2], d[3]))
    for k in sorted(mp)[:30]:
        print("   %-10s ← 基原 %-8s（标记 %s）" % (k, mp[k]["base"], mp[k]["marker"]))
    print("已写出 -> %s" % OUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
