# -*- coding: utf-8 -*-
"""一次性探针：52 味药典缺口，现有规则兜住多少、COCONUT 能接多少。"""
from __future__ import annotations

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
sys.path.insert(0, str(STAGE / "sources"))
sys.path.insert(0, str(STAGE / "core"))
Z = STAGE / "reports" / "_probe_net" / "indkb.zip"
SUB = "一部/药材和饮片/"


def main() -> None:
    import sqlite3
    import formula as F
    import coconut as CC

    c = sqlite3.connect("file:D:/TCMAI/tcm.db?mode=ro", uri=True)
    names = {r[0] for r in c.execute("SELECT name_cn FROM herbs")}
    c.close()
    z = zipfile.ZipFile(Z)
    md = [i.filename for i in z.infolist() if i.filename.endswith(".md") and SUB in i.filename]
    chp = {Path(n).stem for n in md}
    missing = sorted(chp - names)

    dn, da = F._names_alias()
    rule_ok, real_gap = [], []
    for nm in missing:
        base = re.split(r"[（(]", nm)[0]
        got = F._resolve_one(base, dn, da)
        if got:
            rule_ok.append((nm, got))
        else:
            real_gap.append(nm)
    print("药典缺口 %d 味：" % len(missing))
    print("  ★ 现有规则已能落到基原的 = %d（炮制品/别名，不用补库）" % len(rule_ok))
    print("     样例：", rule_ok[:10])
    print("  ★ 真正缺的 = %d：%s" % (len(real_gap), real_gap))

    print()
    print("真缺口里，药典正文的拉丁学名能不能在 COCONUT 找到对应物种：")
    hit = misslat = nolat = 0
    for nm in real_gap:
        fn = next((n for n in md if Path(n).stem == nm), None)
        if not fn:
            continue
        t = re.sub(r"\s+", " ", z.read(fn).decode("utf-8", "replace"))
        m = re.search(r"\b([A-Z][a-z]{3,})\s+([a-z]{4,})\b", t)
        if not m:
            nolat += 1
            continue
        lat = "%s %s" % (m.group(1), m.group(2))
        sp, how = CC.looks_like_species(lat)
        if sp:
            hit += 1
            print("   %-12s %-28s → COCONUT: %s" % (nm, lat, sp))
        else:
            misslat += 1
            print("   %-12s %-28s → COCONUT 里没有" % (nm, lat))
    print()
    print("汇总：接上 COCONUT = %d ｜ COCONUT 里没有 = %d ｜ 抓不到拉丁 = %d"
          % (hit, misslat, nolat))


if __name__ == "__main__":
    main()
