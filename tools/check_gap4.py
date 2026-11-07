# -*- coding: utf-8 -*-
r"""药典「真缺口」里最后 4 味的**本地**核对（不联网）。

四味是（第七十四轮交接）：
   哈蟆油（动物药，COCONUT 是植物/天然产物库）、小驳骨（Gendarussa vulgaris）、
   艾片(左旋龙脑)（加工品）、一个含生僻字的条目。

本脚本把「能不能救」逐条查实（只读两个库）：
   * COCONUT 里有没有对应**物种**（含异写/近似拼写）；
   * 若是加工品/单体，tcm.db 的 **compounds** 里有没有这个**化合物**（按名字）；
   * 都查不到 → 如实记「本地无源」，并说明该走什么路子。

用法：``python tools\check_gap4.py``
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

STAGE = Path(__file__).resolve().parent.parent
TCM = "file:D:/TCMAI/tcm.db?mode=ro"


def main() -> int:
    import sqlite3
    import json
    sp = json.loads((STAGE / "data" / "herb_species.json").read_text(encoding="utf-8"))
    # 1) 先看「含生僻字」的那一条到底是哪个：药典条目名里出现非 GB2312 常用字的
    rare = []
    for nm in sp:
        for ch in nm:
            if ord(ch) > 0x9FFF or ch in "䗪蜣蟅":
                rare.append(nm)
                break
    print("含生僻字的药典条目（本地 species 表里扫到 %d 个）：%s" % (len(rare), rare or "—"))

    # coconut.db：成分在 compounds，物种在 species_compound（species 列）
    coconut = sqlite3.connect("file:D:/TCMAI/coconut.db?mode=ro", uri=True)
    out = {"generated_for": "药典真缺口最后 4 味（本地核对）", "items": []}

    def sp_hits(kw):
        return [r[0] for r in coconut.execute(
            "SELECT DISTINCT species FROM species_compound "
            "WHERE lower(species) LIKE ? LIMIT 6", ("%" + kw + "%",)).fetchall()]

    checks = [
        ("小驳骨", "Gendarussa vulgaris Nees（药典正文）", "gendarussa", "g.vulgaris"),
        ("哈蟆油", "Rana dybowskii（蛙科动物）", "dybowskii", "rana dybowskii"),
        ("艾片(左旋龙脑)", "无拉丁（加工品：(1S)-龙脑）", "borneol", ""),
        ("土鳖虫(䗪虫)", "含生僻字；地鳖（昆虫）", "eupolyphaga", "steleophaga"),
    ]
    for name, src, kw1, kw2 in checks:
        h1 = sp_hits(kw1) if kw1 else []
        h2 = sp_hits(kw2) if kw2 else []
        out["items"].append({"herb": name, "latin_in_chp": src,
                             "coconut_species_like_%s" % kw1: h1,
                             "coconut_species_like_%s" % kw2: h2 if kw2 else "—"})
        print("  %-14s CHP: %-34s COCONUT: %s %s"
              % (name, src, h1 or "（无）", ("  /  " + str(h2)) if h2 else ""))
    coconut.close()

    db = sqlite3.connect(TCM, uri=True)
    comp = db.execute("SELECT name_en, formula, inchi_key FROM compounds "
                      "WHERE lower(name_en) LIKE '%trimethyl%bicyclo%' "
                      "AND formula = 'C10H18O' LIMIT 3").fetchall()
    print()
    print("  tcm.db 单体层：龙脑 C10H18O → %s" % (comp or "（无）"))
    out["borneol_in_tcmdb"] = comp
    # 这些药材在库里有没有（决定补丁是否必要）
    for name in ("小驳骨", "哈蟆油", "艾片(左旋龙脑)", "土鳖虫(䗪虫)"):
        n = db.execute("SELECT COUNT(*) FROM herbs WHERE name_cn = ?", (name,)).fetchone()[0]
        print("  tcm.db herbs 里 %-14s → %s" % (name, "有" if n else "缺"))
    db.close()

    outp = STAGE / "data" / "gap4_findings.json"
    outp.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print()
    print("  结论写到 %s" % outp)
    print("  · 能本地救的（物种存在/单体存在）照救；救不了的如实记『本地无源』——"
          "不编数据、不用别的东西顶替。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
