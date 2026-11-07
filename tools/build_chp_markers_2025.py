# -*- coding: utf-8 -*-
r"""从《中国药典 2025 版》知识库（cliviali/Independent-KBs 逐条 Markdown）抽取判据。

与 2020 版（PPRC docx）同一目标：药材 → 含量测定/鉴别成分 → 限量 + 出处。
数据源质量更高：结构化标题（## 含量测定）、[[wikilink]]（需剥壳）、**加粗**、
表格；每条带官方出处 URL（蒲公英 db2.ouryao.com/yd2025）。

输出: reports\chp_markers_2025\chp2025_markers.jsonl（含 part/url/edition 字段）
      reports\chp_markers_2025\summary.json
只读 zip；不发网络请求。
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
ZIP = STAGE / "reports" / "_probe_net" / "indkb.zip"
ROOT = "Independent-KBs-master/药典2025知识库_最终版/一部/"
OUT_DIR = STAGE / "reports" / "chp_markers_2025"

sys.path.insert(0, str(STAGE / "tools"))
from build_chp_markers import parse_limit_rows, parse_identify_rows   # noqa: E402

WIKI = re.compile(r"\[\[([^|\]]+)\|([^\]]+)\]\]")
WIKI2 = re.compile(r"\[\[([^\]]+)\]\]")
HEADING = re.compile(r"^(#{2,6})\s*(.+?)\s*$")


def strip_md(t: str) -> str:
    # 全角方括号变体先归一到 ASCII（源库混用）
    t = t.replace("［［", "[[").replace("］］", "]]").replace("［", "[").replace("］", "]")
    # 源库存在嵌套 wikilink（如 [[[[朱砂]]根]]）——循环剥壳直到稳定
    for _ in range(5):
        new = WIKI.sub(r"\2", t)
        new = WIKI2.sub(r"\1", new)
        if new == t:
            break
        t = new
    return t.replace("**", "")


def front_matter(t: str):
    m = re.match(r"^---\n(.*?)\n---\n", t, re.S)
    meta = {}
    if m:
        for line in m.group(1).splitlines():
            mm = re.match(r"([A-Za-z_]+):\s*\"?(.*?)\"?\s*$", line)
            if mm:
                meta[mm.group(1)] = mm.group(2)
        t = t[m.end():]
    return meta, t


def split_sections(t: str):
    lines = t.split("\n")
    secs, cur_h, cur, start = [], None, [], 0
    for i, l in enumerate(lines):
        m = HEADING.match(l)
        if m:
            if cur:
                secs.append((cur_h, start, "\n".join(cur)))
            cur_h, cur, start = m.group(2).strip(), [], i
        else:
            cur.append(l)
    if cur:
        secs.append((cur_h, start, "\n".join(cur)))
    return secs


def entry_type_of(name: str) -> str:
    if "成方" in name or "制剂" in name:
        return "制剂"
    if "油脂" in name or "提取物" in name:
        return "提取物"
    return "药材"


def normalize_sections(t: str) -> str:
    """源库两种排版混用：`## 含量测定`（标题式）与 `【含量测定】`（行首标记式）。
    把行首【X】标记统一改写成 `## X` 伪标题，后面的正文原样保留。"""
    out = []
    for l in t.split("\n"):
        m = re.match(r"^\s*【([^】]{1,12})】\s*(.*)$", l)
        if m:
            out.append("## " + m.group(1))
            if m.group(2):
                out.append(m.group(2))
        else:
            out.append(l)
    return "\n".join(out)


def main() -> int:
    if not ZIP.exists():
        print("缺 zip：%s" % ZIP)
        return 2
    z = zipfile.ZipFile(ZIP)
    files = [n for n in sorted(z.namelist()) if n.startswith(ROOT) and n.endswith(".md")]
    print("一部 Markdown 条目：%d" % len(files))
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    rows, summ = [], {}
    for name in files:
        t = z.read(name).decode("utf-8", "replace")
        meta, body = front_matter(t)
        title = meta.get("title") or Path(name).stem
        url = meta.get("url", "")
        et = entry_type_of(name)
        n_c = n_i = 0
        in_pian = False
        for h, s, txt in split_sections(normalize_sections(strip_md(body))):
            if h is None:
                continue
            if "饮片" in h:
                in_pian = True
            if "含量测定" in h:
                for r in parse_limit_rows(title, txt, s):
                    r.update(part=("饮片" if in_pian else "药材"), url=url,
                             entry_type=et, edition="2025")
                    rows.append(r)
                    n_c += 1
            elif "鉴别" in h:
                for r in parse_identify_rows(title, txt, s):
                    r.update(part=("饮片" if in_pian else "药材"), url=url,
                             entry_type=et, edition="2025")
                    rows.append(r)
                    n_i += 1
        summ[title] = {"file": name.split(ROOT)[1], "entry_type": et, "url": url,
                       "n_content": n_c, "n_identify": n_i}
    with open(OUT_DIR / "chp2025_markers.jsonl", "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    (OUT_DIR / "summary.json").write_text(
        json.dumps(summ, ensure_ascii=False, indent=1), encoding="utf-8")
    n_with = sum(1 for s0 in summ.values() if s0["n_content"] > 0)
    print("条目 %d（有含量测定 %d）· 行 %d（含量 %d · 鉴别 %d）-> %s"
          % (len(summ), n_with, len(rows),
             sum(1 for r in rows if r["section"] == "含量测定"),
             sum(1 for r in rows if r["section"] == "鉴别"), OUT_DIR))
    for r in rows:
        if r["herb"] == "甘草" and r["section"] == "含量测定":
            print("   [甘草样例] %s %s %s %s%%（part=%s）"
                  % (r["name_raw"], r["relation"], r["value"], r["unit"], r["part"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
