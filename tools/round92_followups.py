#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""第 92 轮的三件收尾（用户 2026-11-04 点名 ①②③）：

  ① 补 2 轮：甘草酸 → 甘草次酸（第 92 轮只跑了 1 轮）
  ② 单煎 vs 合煎：乌头碱单独煎，vs 与甘草酸/甘草苷同锅煎，比单酯型生成
  ③ 换一个方剂：黄芩汤（黄芩 + 白芍 + 甘草 + 大枣），黄芩苷 → 黄芩素（糖苷水解）

口径与第 92 轮相同：产物（InChIKey 前 14 位）+ 路径（台账有那一行）+ 反应族（规则属于文献说的那类）。
文献依据：
  * 黄芩苷（baicalin）在煎煮过程中糖苷键水解生成黄芩素（baicalein），
    见 <https://www.sciencedirect.com/science/article/abs/pii/S0731708510001296> 一类工作；
    本方只引用「煎煮水解成苷元」这一条反应，不引申药效。
  * 甘草酸 2 轮水解的中间体是单葡萄糖醛酸甘草次酸（本地库无此结构，故只能看终点苷元）。
  * 合煎影响乌头碱水解的依据同第 92 轮（参附合煎、四逆汤配伍研究）。

用法：
    python -I tools\\round92_followups.py
输出：reports/formula_followups_20261104.json
"""
from __future__ import annotations

import json
import sqlite3
import sys
import time
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

ROOT = Path(__file__).resolve().parent.parent
for _p in (ROOT / "core", ROOT / "tools", ROOT / "conditions"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import validate_literature_conversions as V          # noqa: E402
import validate_formula_decoction as vfd              # noqa: E402

DB = "file:D:/TCMAI/tcm.db?mode=ro"
OUT = ROOT / "reports" / "formula_followups_20261104.json"

ID = {
    "Glycyrrhizin": "HBIN028191",
    "Glycyrrhetinic acid": "HBIN028184",
    "Aconitine": "HBIN014582",
    "Benzoylaconine": "HBIN017810",
    "Liquiritin": "HBIN033383",
    "Baicalin": "HBIN017516",
    "Baicalein": "HBIN017508",
    "Paeoniflorin": "HBIN038606",
}


def db():
    return sqlite3.connect(DB, uri=True)


def seed(con, name, herb):
    r = con.execute("select smiles, formula from compounds where ingredient_id=?",
                    (ID[name],)).fetchone()
    if not r:
        raise SystemExit("库里没有 %s (%s)" % (name, ID[name]))
    return {"name": name, "smiles": r[0], "formula": r[1], "herb": herb}


def hop_rules(h):
    out = [h.rule] if h.rule else []
    for x in (getattr(h, "alt_rules", "") or "").split(","):
        x = x.strip()
        if x and x not in out:
            out.append(x)
    return out


def hits_for(con, hops, target_name, prefixes):
    """目标结构的所有跳 + 是否有符合文献反应族的规则（主规则与 also_rules 取并集）。"""
    tsmi = con.execute("select smiles from compounds where ingredient_id=?",
                       (ID[target_name],)).fetchone()[0]
    want = V.full_inchikey(tsmi)[:14].upper()
    out = []
    for h in hops:
        try:
            if V.full_inchikey(h.product)[:14].upper() == want:
                out.append(h)
        except Exception:
            continue
    def fam(r):
        r = (r or "").lower()
        return any(p.lower() in r for p in prefixes)
    fam_rules = sorted({x for h in out for x in hop_rules(h) if fam(x)})
    return out, fam_rules


def case_line(label, hops, fam_rules):
    if not hops:
        return "%s: not_found" % label
    rounds = sorted({h.round for h in hops})
    if fam_rules:
        return "%s: consistent（%d 条跳，轮次 %s，规则 %s）" % (
            label, len(hops), rounds, ",".join(fam_rules))
    return "%s: product_only（%d 条跳，轮次 %s，规则 %s）" % (
        label, len(hops), rounds, ",".join(sorted({h.rule for h in hops}))[:80])


def main() -> int:
    con = db()
    res = {"generated_at": time.strftime("%Y-%m-%d %H:%M:%S"), "cases": {}}

    # ---------------- ① 甘草酸 2 轮 → 甘草次酸
    print("== ① 甘草酸 2 轮 ==")
    s = [seed(con, "Glycyrrhizin", "甘草")]
    hops, secs = vfd.run_batch(s, "煎煮", max_pairs=24, rounds=2, max_products_per_pair=12)
    hs, fam = hits_for(con, hops, "Glycyrrhetinic acid", ("hydrolysis_glycoside",))
    print("   2 轮：%d 跳 / %.1f s；%s" % (len(hops), secs, case_line("甘草次酸", hs, fam)))
    res["cases"]["①_glycyrrhizin_2rounds"] = {
        "status": "consistent" if (hs and fam) else ("product_only" if hs else "not_found"),
        "n_hops": len(hops), "seconds": secs,
        "rounds_seen": sorted({h.round for h in hs}) if hs else [],
        "rules": fam or sorted({h.rule for h in hs})[:5],
        "target": "甘草次酸 C30H46O4",
    }

    # ---------------- ② 单煎 vs 合煎（乌头碱）
    print("== ② 单煎 vs 合煎 ==")
    def count(seeds, tag):
        hh, ss = vfd.run_batch(seeds, "煎煮", max_pairs=24)
        hs2, fam2 = hits_for(con, hh, "Benzoylaconine", ("hydrolysis_ester",))
        n_mono = sum(1 for x in hh for r in hop_rules(x) if "hydrolysis_ester" in r.lower())
        print("   %-6s %d 跳 / %.1f s；苯甲酰乌头原碱 %d 条跳，反应族%s；水解酯类跳总数 %d"
              % (tag, len(hh), ss, len(hs2), "符合" if fam2 else "不符合", n_mono))
        return {"n_hops": len(hh), "seconds": ss, "n_target_hops": len(hs2),
                "family_ok": bool(fam2), "n_hydrolysis_ester_hops": n_mono}
    dan = count([seed(con, "Aconitine", "附子")], "单煎")
    he = count([seed(con, "Aconitine", "附子"), seed(con, "Glycyrrhizin", "甘草"),
                seed(con, "Liquiritin", "甘草")], "合煎")
    res["cases"]["②_dan_vs_he"] = {"dan_jian": dan, "he_jian": he}

    # ---------------- ③ 黄芩汤：黄芩苷 → 黄芩素
    print("== ③ 黄芩汤（黄芩+白芍+甘草+大枣）==")
    herbs = {r[0] for r in con.execute(
        "select herb_id from herbs where name_cn in ('黄芩','白芍','甘草','大枣')")}
    print("   方内药味命中 %d 个 herb_id" % len(herbs))
    s3 = [seed(con, "Baicalin", "黄芩"), seed(con, "Paeoniflorin", "白芍"),
          seed(con, "Glycyrrhizin", "甘草")]
    hops3, secs3 = vfd.run_batch(s3, "煎煮", max_pairs=24)
    hs3, fam3 = hits_for(con, hops3, "Baicalein", ("hydrolysis_glycoside",))
    print("   %d 跳 / %.1f s；%s" % (len(hops3), secs3, case_line("黄芩素", hs3, fam3)))
    res["cases"]["③_huangqin_tang"] = {
        "status": "consistent" if (hs3 and fam3) else ("product_only" if hs3 else "not_found"),
        "n_hops": len(hops3), "seconds": secs3,
        "rounds_seen": sorted({h.round for h in hs3}) if hs3 else [],
        "rules": fam3 or sorted({h.rule for h in hs3})[:5],
        "target": "黄芩素 C15H10O5",
        "n_herbs_found": len(herbs),
    }

    Path(OUT).write_text(json.dumps(res, ensure_ascii=False, indent=2), encoding="utf-8")
    print("写出：%s" % OUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
