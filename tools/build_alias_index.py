# -*- coding: utf-8 -*-
r"""建**多候选**别名索引（用户 2026-10-16 要求）。

为什么要重做：现有的 ``herb_aliases_map.json`` 把"一个别名指向多个规范名"的
**5,885 个**情形用启发式**自动选了一个**（脚本 ``D:\TCMAI\scripts\build_alias_map.py``
的 ``pick_canonical``）。可同一俗名在不同地区指不同植物是真实情况 ——

    龙胆草 → 小龙胆草 / 湿生扁蕾 / 矮脚苦蒿 / 红花龙胆 / 耳草 / 贵州獐牙菜 / 龙胆
    鱼胆草 → 小飞蓬 / 瓜子金 / 矮脚苦蒿 / 苦玄参 / 落地小金钱 / 金龙胆草 / 青鱼胆草

本脚本**保留全部候选**，带辞典来源与权威度，输出 ``data/alias_index.json``。
手工整理那部分**直接 import 用户脚本**取 ``MANUAL``，不重打一遍。

数据源与优先级（沿用用户脚本的设计）：
    1. ``D:\TCMAI\scripts\build_alias_map.py`` 的 MANUAL（最高）
    2. NTU《中文药名同义词表》ChineseDrugEthnonymsSynonymyTable.xlsx（50,607 行）
    3. ``tcm.db`` 的 ``herbs.alias``（兜底）

用法：``python tools/build_alias_index.py``
"""
from __future__ import annotations

import json
import sqlite3
import sys
from collections import defaultdict
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

STAGE = Path(r"D:\ProgramData\DSHNS\chemreact-staging")
TCMAI = Path(r"D:\TCMAI")
XLS = TCMAI / "data" / "ChineseDrugEthnonymsSynonymyTable.xlsx"
TCM = TCMAI / "tcm.db"
OUT = STAGE / "data" / "alias_index.json"

DICT_RANK = (
    ("中国药典", 0),
    ("中华本草", 1),
    ("中药大辞典", 2),
    ("全国中草药汇编", 3),
)


def dict_rank(dic: str) -> int:
    best = 9
    for key, r in DICT_RANK:
        if key in (dic or ""):
            best = min(best, r)
    return best


def load_manual() -> dict:
    """直接复用用户脚本里的 MANUAL 常量（不重打）。"""
    sys.path.insert(0, str(TCMAI / "scripts"))
    try:
        import build_alias_map as BAM          # noqa: N813
        return dict(getattr(BAM, "MANUAL", {}))
    except Exception as ex:                     # noqa: BLE001 —— 打印，不静默
        print("   [warn] 读不到用户脚本的 MANUAL（%s: %s），跳过" % (type(ex).__name__, ex))
        return {}


def load_excel():
    """→ {别名: {规范名: {"n": 次数, "dicts": {辞典: 次数}}}}"""
    import openpyxl
    wb = openpyxl.load_workbook(XLS, read_only=True, data_only=True)
    ws = wb[wb.sheetnames[0]]
    first = True
    out = defaultdict(lambda: defaultdict(lambda: {"n": 0, "dicts": defaultdict(int)}))
    rows = 0
    for row in ws.iter_rows(values_only=True):
        if first:
            first = False
            continue
        if len(row) < 4 or not row[1] or not row[3]:
            continue
        primary = str(row[1]).strip()
        dic = str(row[2] or "").strip()
        alt = str(row[3]).strip()
        if not primary or not alt or primary == alt:
            continue
        cell = out[alt][primary]
        cell["n"] += 1
        cell["dicts"][dic] += 1
        rows += 1
    wb.close()
    print("   Excel %d 行 → %d 个别名、%d 个规范名"
          % (rows, len(out), len({p for v in out.values() for p in v})))
    return out


def load_tcmdb():
    conn = sqlite3.connect("file:" + str(TCM).replace("\\", "/") + "?mode=ro", uri=True)
    try:
        names = {r[0]: r[1] for r in conn.execute("SELECT name_cn, herb_id FROM herbs")}
        out = defaultdict(lambda: defaultdict(lambda: {"n": 0, "dicts": defaultdict(int)}))
        for name, alias in conn.execute("SELECT name_cn, COALESCE(alias,'') FROM herbs"):
            for a in str(alias).replace("；", ";").replace("、", ";").split(";"):
                a = a.strip()
                if not a or a == name:
                    continue
                cell = out[a][name]
                cell["n"] += 1
                cell["dicts"]["tcm.db"] += 1
        return out, names
    finally:
        conn.close()


def main() -> int:
    print("建别名索引（多候选）……")
    manual = load_manual()
    print("   手工整理 %d 条" % len(manual))
    ex = load_excel()
    db, names = load_tcmdb()
    print("   tcm.db 别名 %d 个（库内药材 %d 味）" % (len(db), len(names)))

    merged = defaultdict(lambda: defaultdict(lambda: {"n": 0, "dicts": defaultdict(int)}))
    for src in (db, ex):
        for alias, cands in src.items():
            for canon, cell in cands.items():
                tgt = merged[alias][canon]
                tgt["n"] += cell["n"]
                for d, c in cell["dicts"].items():
                    tgt["dicts"][d] += c
    for alias, canon in manual.items():
        merged[alias][canon]["n"] += 1000
        merged[alias][canon]["dicts"]["MANUAL"] += 1

    by_alias = {}
    n_multi = n_single = n_in_db = 0
    for alias, cands in merged.items():
        if alias in names:
            continue
        items = []
        for canon, cell in cands.items():
            dic = (max(cell["dicts"].items(), key=lambda kv: kv[1])[0]
                   if cell["dicts"] else "")
            items.append({"canonical": canon, "n": cell["n"], "dict": dic,
                          "rank": dict_rank(dic),
                          "herb_id": names.get(canon, ""),
                          "in_db": canon in names})
        items.sort(key=lambda x: (0 if x["in_db"] else 1, x["rank"],
                                  -x["n"], x["canonical"]))
        by_alias[alias] = items
        n_multi += 1 if len(items) > 1 else 0
        n_single += 1 if len(items) == 1 else 0
        n_in_db += 1 if items and items[0]["in_db"] else 0

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(
        {"meta": {"n_alias": len(by_alias), "n_multi": n_multi,
                  "n_single": n_single, "n_first_in_db": n_in_db,
                  "sources": ["MANUAL(用户脚本)",
                              "NTU ChineseDrugEthnonymsSynonymyTable",
                              "tcm.db herbs.alias"]},
         "by_alias": by_alias}, ensure_ascii=False, indent=0, sort_keys=True),
        encoding="utf-8")
    print("\n结果：别名 %d ｜ 多候选 %d ｜ 单候选 %d ｜ 首选在库内 %d"
          % (len(by_alias), n_multi, n_single, n_in_db))
    print("已写出 -> %s（%.2f MB）" % (OUT, OUT.stat().st_size / 1048576))
    print("\n抽查：")
    for k in ("龙胆草", "鱼胆草", "生地", "元参", "川军", "十字草", "槐米", "铁杆蒿"):
        v = by_alias.get(k)
        if not v:
            print("   %-6s → （未收录）" % k)
            continue
        print("   %-6s → %s" % (k, " ｜ ".join(
            "%s%s%s" % (x["canonical"], "*" if x["in_db"] else "（库外）",
                        "" if x["rank"] >= 9 else "[%s]" % x["dict"][:6])
            for x in v[:5])))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
