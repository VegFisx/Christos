# -*- coding: utf-8 -*-
r"""生成「药典缺 52 味」的**补库补丁文件**（第七十五轮；**不碰用户的库**）。

背景（实测）：药典 2025 一部「药材和饮片」共 **617** 条，`tcm.db` 里缺 **52** 味；
其中大部分是**炮制品**（姜半夏 / 制何首乌 / 大蓟炭…，独立药材，不许替换成基原），
其余是冷门药材（杠板归 / 翼首草 / 蓝布正…）。

用户 2026-10-16：「等用户点头……不直接改他的库」→ 本脚本**只产出补丁文件**：

  data\patch_missing_herbs\
      missing_herbs.json     逐条明细（名称 / 类别 / 拉丁 / 物种 / 出处 / 缺失字段）
      patch_tcmdb.sql        INSERT 语句（herb_id 用 PATCH 前缀，绝不与爬虫编号冲突）
      rollback_tcmdb.sql     对应的 DELETE 语句（后悔药）
      README.md              怎么备份 / 怎么应用 / 怎么核对 / 这个补丁**不做什么**

纪律：
  * 一律**从数据里取**（药典知识库 zip + `data\herb_species.json` + `data\chp_processed.json`），
    不手写任何药材字段；取不到的字段留 NULL 并在明细里标 `missing`；
  * `tcm.db` 只读打开（`mode=ro`），脚本绝不写入；
  * 补丁**不造成分数据** —— 成分仍走软件自带的「药典拉丁学名 → COCONUT 物种」兜底。

用法：``python tools\build_missing_herbs_patch.py``
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

STAGE = Path(__file__).resolve().parent.parent
Z = STAGE / "reports" / "_probe_net" / "indkb.zip"
SUB = "一部/药材和饮片/"
OUTD = STAGE / "data" / "patch_missing_herbs"
TCM = "file:D:/TCMAI/tcm.db?mode=ro"

_LATIN = re.compile(r"([A-Z][a-z]{3,}\s+[a-z][a-z\-]{2,})")
_PART = re.compile(r"的(干燥|鲜|除去外皮)[^，。；]{0,12}?"
                   r"(根茎|根|全草|地上部分|叶|茎|花|果实|种子|皮|心材|藤茎|茎髓|"
                   r"块根|鳞茎|菌核|子实体|树脂|分泌物|角|输卵管|胆|壳|体|髓|茎叶)")
_FUNC = re.compile(r"【\s*功能与主治\s*】(.*?)(?=【|$)", re.S)


def unwrap(s: str) -> str:
    for _ in range(6):
        new = re.sub(r"\[\[([^\[\]]*)\]\]", r"\1", s)
        if new == s:
            break
        s = new
    return s


def main() -> int:
    import sqlite3
    c = sqlite3.connect(TCM, uri=True)
    have = {r[0] for r in c.execute("SELECT name_cn FROM herbs")}
    c.close()

    z = zipfile.ZipFile(Z)
    entries = {}
    for i in z.infolist():
        if i.filename.endswith(".md") and SUB in i.filename:
            txt = z.read(i.filename).decode("utf-8", errors="replace")
            entries[Path(i.filename).stem] = {"text": txt, "zip_path": i.filename}
    missing = sorted(set(entries) - have)

    sp = json.loads((STAGE / "data" / "herb_species.json").read_text(encoding="utf-8"))
    # 结构：扁平字典 {药材名: {"latin_raw": [...], "species": [...], "url": ...}}
    sp_map = sp if isinstance(sp, dict) else {}
    proc = json.loads((STAGE / "data" / "chp_processed.json").read_text(encoding="utf-8"))
    # chp_processed.json 结构：{"names": [...], "map": {"姜半夏": {"base": "半夏", ...}}}
    proc_names = set(proc.get("names") or [])
    proc_base = {k: (v or {}).get("base") for k, v in (proc.get("map") or {}).items()}

    rows, stats = [], {"炮制品": 0, "其它": 0, "有拉丁": 0, "有物种": 0, "有部位": 0}
    for n in missing:
        e = entries[n]
        t = unwrap(e["text"])
        m = _LATIN.search(t)
        latin = m.group(1) if m else ""
        mp = _PART.search(t)
        part = mp.group(0) if mp else ""
        mf = _FUNC.search(t)
        func = re.sub(r"\s+", " ", mf.group(1)).strip()[:120] if mf else ""
        sm = sp_map.get(n) or {}
        species = "、".join(sm.get("species") or [])
        chp_url = sm.get("url") or ""
        is_proc = n in proc_names
        kind = "炮制品" if is_proc else "其它"
        stats[kind] += 1
        stats["有拉丁"] += 1 if latin else 0
        stats["有物种"] += 1 if species else 0
        stats["有部位"] += 1 if part else 0
        rows.append({
            "name_cn": n, "kind": kind,
            "base": proc_base.get(n) or "",
            "latin": latin, "species": species, "use_part": part,
            "function": func,
            "source": "中国药典2025版一部·药材和饮片",
            "chp_url": chp_url,
            "zip_path": e["zip_path"],
            "missing": [k for k, v in (("latin", latin), ("species", species),
                                       ("use_part", part), ("function", func)) if not v],
        })

    OUTD.mkdir(parents=True, exist_ok=True)
    (OUTD / "missing_herbs.json").write_text(json.dumps(
        {"count": len(rows), "source": "药典2025一部·药材和饮片（617 条）vs tcm.db herbs",
         "stats": stats, "items": rows}, ensure_ascii=False, indent=1), encoding="utf-8")

    ins = ["-- chemreact 补库补丁（药典缺 52 味）：herb 元数据",
           "-- ★ 应用前请先备份 tcm.db；本文件由 tools\\build_missing_herbs_patch.py 生成",
           "-- ★ 本补丁**不含成分数据**：成分仍走软件自带的「药典拉丁学名 → COCONUT 物种」兜底",
           "BEGIN TRANSACTION;"]
    dele = ["-- 回滚：删掉本补丁插入的行", "BEGIN TRANSACTION;"]
    for i, r in enumerate(rows, 1):
        hid = "PATCH%05d" % i
        vals = [hid, r["name_cn"], r["latin"] or None, r["use_part"] or None,
                r["function"] or None, "chemreact补丁:药典2025一部"]
        lit = ", ".join("NULL" if v is None else "'" + str(v).replace("'", "''") + "'"
                        for v in vals)
        ins.append("INSERT INTO herbs (herb_id, name_cn, latin, use_part, function, alias) "
                   "VALUES (%s);" % lit)
        dele.append("DELETE FROM herbs WHERE herb_id = '%s';" % hid)
    ins += ["COMMIT;", "",
            "-- 核对：SELECT COUNT(*) FROM herbs WHERE herb_id LIKE 'PATCH%%';  -- 期望 %d"
            % len(rows)]
    dele += ["COMMIT;"]
    (OUTD / "patch_tcmdb.sql").write_text("\n".join(ins) + "\n", encoding="utf-8")
    (OUTD / "rollback_tcmdb.sql").write_text("\n".join(dele) + "\n", encoding="utf-8")

    # ★ 推荐子集：只导**有拉丁学名**的那批复（成分能走 COCONUT 物种兜底）
    sub = [r for r in rows if r["latin"]]
    ins2 = ["-- 推荐子集：只导**有拉丁学名**的 %d 味（成分可走「药典拉丁学名→COCONUT 物种」）"
            % len(sub),
            "-- ★ 应用前先备份 tcm.db；herb_id 用 PATCH 前缀", "BEGIN TRANSACTION;"]
    del2 = ["-- 回滚（子集）", "BEGIN TRANSACTION;"]
    for i, r in enumerate(sub, 1):
        hid = "PATCHL%04d" % i
        vals = [hid, r["name_cn"], r["latin"], r["use_part"], r["function"],
                "chemreact补丁(有拉丁):药典2025一部"]
        lit = ", ".join("NULL" if v is None else "'" + str(v).replace("'", "''") + "'"
                        for v in vals)
        ins2.append("INSERT INTO herbs (herb_id, name_cn, latin, use_part, function, alias) "
                    "VALUES (%s);" % lit)
        del2.append("DELETE FROM herbs WHERE herb_id = '%s';" % hid)
    ins2 += ["COMMIT;", ""]
    del2 += ["COMMIT;"]
    (OUTD / "patch_tcmdb_latin-only.sql").write_text("\n".join(ins2) + "\n", encoding="utf-8")
    (OUTD / "rollback_tcmdb_latin-only.sql").write_text("\n".join(del2) + "\n", encoding="utf-8")
    (OUTD / "README.md").write_text(
        "# 补库补丁（药典缺 %d 味）\n\n"
        "> **仅库主维护者使用。** 软件不会读取或应用本补丁；终端用户没有数据库写入入口。\n"
        "> 只有库主在明确确认并备份后，才由维护者执行下面的 SQL。\n\n"
        "> 由 `tools\\build_missing_herbs_patch.py` 生成；**没有改动你的库**，只是一个文件包。\n\n"
        "## 里面有什么\n\n"
        "* `missing_herbs.json` —— 逐条明细：药典条目名、类别（炮制品/其它）、拉丁学名、\n"
        "  对应物种（COCONUT）、药用部位、功能主治、出处（药典 2025 一部）、以及缺哪些字段；\n"
        "* `patch_tcmdb.sql` —— INSERT 语句；`herb_id` 用 `PATCH` 前缀，**不会和爬虫的编号冲突**；\n"
        "* `rollback_tcmdb.sql` —— 对应的 DELETE，后悔药。\n\n"
        "## 库主维护流程（不是终端用户流程）\n\n"
        "```powershell\n"
        "# 1) 先备份（关掉爬虫/VS Code 里的写入进程再做）\n"
        "Copy-Item D:\\TCMAI\\tcm.db D:\\TCMAI\\tcm.db.bak-20261016\n"
        "# 2) 应用补丁\n"
        "sqlite3 D:\\TCMAI\\tcm.db \".read data\\patch_missing_herbs\\patch_tcmdb.sql\"\n"
        "# 3) 核对（期望 %d）\n"
        "sqlite3 D:\\TCMAI\\tcm.db \"SELECT COUNT(*) FROM herbs WHERE herb_id LIKE 'PATCH%%';\"\n"
        "```\n\n"
        "## 这个补丁**不做什么**\n\n"
        "* 不造成分数据：这些药材的成分仍由软件用「药典正文拉丁学名 → COCONUT 物种」兜底；\n"
        "* 不改任何既有行：只插入 52 行新行；\n"
        "* 不替你做决定：要不要导入、导入哪几条（比如动物药 `哈蟆油` 你可以只导其中一部分）由你定。\n\n"
        "## 明细\n\n"
        "| # | 药典条目 | 类别 | 基原 | 拉丁学名 | 物种(COCONUT) | 缺 |\n"
        "|---|---|---|---|---|---|---|\n"
        + "\n".join("| %d | %s | %s | %s | %s | %s | %s |"
                    % (i, r["name_cn"], r["kind"], r["base"] or "—",
                       r["latin"] or "—", r["species"] or "—",
                       "、".join(r["missing"]) or "—")
                    for i, r in enumerate(rows, 1))
        + "\n", encoding="utf-8")

    print("=" * 96)
    print("补库补丁已生成（**未改动你的库**）：%s" % OUTD)
    print("  缺口 %d 味：炮制品 %d ｜ 其它 %d" % (len(rows), stats["炮制品"], stats["其它"]))
    print("  能带拉丁学名 %d ｜ 能接 COCONUT 物种 %d ｜ 能带药用部位 %d"
          % (stats["有拉丁"], stats["有物种"], stats["有部位"]))
    print("  文件：missing_herbs.json ｜ patch_tcmdb.sql ｜ rollback_tcmdb.sql ｜ README.md")
    print("  另有推荐子集：patch_tcmdb_latin-only.sql（%d 味，全部带拉丁学名）" % len(sub))
    print()
    for r in rows[:6]:
        print("   %-12s %-6s 拉丁=%-24s 物种=%s"
              % (r["name_cn"], r["kind"], r["latin"] or "—", r["species"] or "—"))
    print("   … 共 %d 味" % len(rows))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
