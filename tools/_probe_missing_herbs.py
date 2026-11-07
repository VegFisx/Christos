# -*- coding: utf-8 -*-
"""一次性探针（只读）：tcm.db 到底缺多少"正经药材"，以及药典能不能补它。

Q1 别名表里的**规范名**（NTU《中文药名同义词表》的 PrimaryDrugName）有多少不在 tcm.db
Q2 其中有多少是**药典 2025 一部「药材和饮片」**收载的（= 真正的缺口，不是冷门异名）
Q3 这些缺口的药典条目里有没有【来源】拉丁学名（决定能否接到 COCONUT）
"""
from __future__ import annotations

import json
import re
import sqlite3
import sys
import zipfile
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

STAGE = Path(r"D:\ProgramData\DSHNS\chemreact-staging")
Z = STAGE / "reports" / "_probe_net" / "indkb.zip"
SUB = "一部/药材和饮片/"


def main() -> None:
    c = sqlite3.connect("file:D:/TCMAI/tcm.db?mode=ro", uri=True)
    names = {r[0] for r in c.execute("SELECT name_cn FROM herbs")}
    c.close()
    ai = json.loads((STAGE / "data" / "alias_index.json").read_text(encoding="utf-8"))
    prim = set()
    for cands in ai["by_alias"].values():
        for x in cands:
            prim.add(x["canonical"])
    prim = {p for p in prim if re.search(r"[\u4e00-\u9fff]", p)}
    miss = {p for p in prim if p not in names}
    print("[Q1] 别名表的规范名 %d 个，其中不在 tcm.db 的 = %d（%.1f%%）"
          % (len(prim), len(miss), 100.0 * len(miss) / max(1, len(prim))))

    z = zipfile.ZipFile(Z)
    chp_md = [i.filename for i in z.infolist()
              if i.filename.endswith(".md") and SUB in i.filename]
    chp_names = {Path(n).stem for n in chp_md}
    print("[Q2] 药典 2025 一部「药材和饮片」= %d 条" % len(chp_names))
    chp_missing = chp_names - names
    print("     其中 **不在 tcm.db** 的 = %d —— ★ 这就是「正经药材」的缺口"
          % len(chp_missing))
    print("     样例：", sorted(chp_missing)[:40])
    inter_miss = (chp_missing & prim)
    print("     这些缺口里，别名表也认得的 = %d" % len(inter_miss))

    # ★ 药典不写【来源】小标题，拉丁学名直接写在"本品为…植物 X 的干燥…"正文里。
    print("[Q3] 缺口条目正文里能不能抓到拉丁双名法（决定能否接 COCONUT）")
    ok = 0
    fail = []
    samples = []
    for nm in sorted(chp_missing):
        fn = next((n for n in chp_md if Path(n).stem == nm), None)
        if not fn:
            fail.append((nm, "无文件"))
            continue
        t = z.read(fn).decode("utf-8", "replace")
        if "内容获取失败" in t:
            fail.append((nm, "内容获取失败"))
            continue
        body = re.sub(r"\s+", " ", t)
        latin = re.search(r"\b([A-Z][a-z]{3,})\s+([a-z]{4,})\b", body)
        if latin:
            ok += 1
            if len(samples) < 10:
                samples.append((nm, latin.group(0)))
        else:
            fail.append((nm, "无拉丁"))
    print("     能抓到拉丁学名的 = %d / %d" % (ok, len(chp_missing)))
    for s in samples:
        print("       %-14s → %s" % s)
    if fail:
        print("     抓不到的 %d 个：%s" % (len(fail), fail[:14]))


if __name__ == "__main__":
    main()
