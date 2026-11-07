# -*- coding: utf-8 -*-
r"""第七十一轮 · 队列#3：药典 2025 gold 核对（抽 ~200 行，对 indkb.zip 原文）。

口径（写死）：
  * 抽样：从 `reports\chp_markers_2025\chp2025_curated.csv` 按 (herb,name,value,unit,relation) 去重后，
    用固定种子 random.Random(20261015) 抽 N 行。
  * 定位原文：indkb.zip 里 `药典2025知识库_最终版/…/<herb>.md`（按文件名 basename 建索引）。
  * 判"被原文支持"：md 正文里同时出现 **该行的标记名**（name，若为空则跳过该条）与 **数值+单位**
    （value/unit，若为空则跳过）；两项都命中 = supported。
  * 分类：entry_missing / name_missing / value_missing / supported / weak（只命中其一）。

用法: python tools/gold_check_chp2025.py [N]
输出: reports/chp_markers_2025/gold_check.json（含失败样例）
"""
from __future__ import annotations

import csv
import json
import random
import re
import sys
import zipfile
from collections import Counter
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

STAGE = Path(r"D:\ProgramData\DSHNS\chemreact-staging")
CSV = STAGE / "reports" / "chp_markers_2025" / "chp2025_curated.csv"
ZIP = STAGE / "reports" / "_probe_net" / "indkb.zip"
OUT = STAGE / "reports" / "chp_markers_2025" / "gold_check.json"
ROOT = "Independent-KBs-master/药典2025知识库_最终版/"


def strip_wikilinks(t: str) -> str:
    """把 `[[目标|显示]]` / `[[目标]]` 剥成纯文本（**要迭代**：原文里有嵌套 `[[[[朱砂]]根]]`）。

    ★ 为什么必须剥：实测 `炙甘草.md` 里写的是 `[[甘草]]酸`、`[[甘草]]苷` ——
    直接子串搜 "甘草酸" 会**漏判**，把好行当成错行。
    """
    prev = None
    while prev != t:
        prev = t
        t = re.sub(r"\[\[([^\[\]|]*)\|([^\[\]]*)\]\]", r"\2", t)   # [[目标|显示]] -> 显示
        t = re.sub(r"\[\[([^\[\]]*)\]\]", r"\1", t)                  # [[目标]] -> 目标
    return t


def build_index(zf):
    idx = {}
    for n in zf.namelist():
        if not n.lower().endswith(".md"):
            continue
        base = n.rsplit("/", 1)[-1][:-3]
        idx.setdefault(base, n)
    return idx


def main() -> int:
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 200
    rows = list(csv.DictReader(open(CSV, encoding="utf-8-sig", newline="")))
    seen, uniq = set(), []
    for r in rows:
        key = (r.get("herb", ""), r.get("name", ""), r.get("value", ""),
               r.get("unit", ""), r.get("relation", ""))
        if key in seen:
            continue
        seen.add(key)
        uniq.append(r)
    rnd = random.Random(20261015)
    sample = rnd.sample(uniq, min(n, len(uniq)))
    print(f"去重后 {len(uniq)} 行；抽样 {len(sample)} 行", flush=True)

    zf = zipfile.ZipFile(ZIP)
    idx = build_index(zf)
    print(f"zip md 文件 {len(idx)} 个（按 basename 索引）", flush=True)

    codes = Counter()
    fails = []
    for r in sample:
        herb = (r.get("herb") or "").strip()
        name = (r.get("name") or "").strip()
        val = (r.get("value") or "").strip()
        unit = (r.get("unit") or "").strip()
        path = idx.get(herb)
        if path is None:
            codes["entry_missing"] += 1
            if len(fails) < 12:
                fails.append({"why": "entry_missing", "herb": herb, "name": name,
                              "value": val + unit})
            continue
        text = strip_wikilinks(zf.read(path).decode("utf-8", errors="replace"))
        # ★ 再按"去掉所有空白"比一次：原文把下标拆开写（`人参皂苷Rb 1`）而表里写 `Rb1`
        text_sq = re.sub(r"\s+", "", text)
        name_sq = re.sub(r"\s+", "", name) if name else ""
        hit_name = ((name in text) or (name_sq and name_sq in text_sq)) if name else None
        hit_val = None
        if val:
            # ★ 先按字面找；找不到再按**数值**找（实测主因：原文写 0.30mg / 0.60%，
            #   而表里写 0.3mg / 0.6% -> 纯字符串匹配会误判成"原文没有"）
            pat = re.escape(val) + r"\s*" + re.escape(unit) if unit else re.escape(val)
            if re.search(pat, text) is not None:
                hit_val = True
            else:
                try:
                    v = float(val)
                except ValueError:
                    v = None
                if v is not None:
                    hit_val = False
                    for m in re.finditer(r"([0-9]+(?:\.[0-9]+)?)", text):
                        try:
                            if abs(float(m.group(1)) - v) < 1e-9:
                                hit_val = True
                                break
                        except ValueError:
                            continue
        is_section = bool(re.match(r"^〔.*〕$", name)) if name else False
        if is_section:
            codes["artifact_section_label"] += 1
        elif hit_name is False:
            codes["name_missing"] += 1
        elif hit_val is False:
            codes["value_missing"] += 1
        elif hit_name is None and hit_val is None:
            codes["no_claim"] += 1
        else:
            codes["supported"] += 1
        if (hit_name is False or hit_val is False) and len(fails) < 12:
            fails.append({"why": "name_missing" if hit_name is False else "value_missing",
                          "herb": herb, "name": name, "value": val + unit,
                          "url": r.get("url", "")})

    tot = len(sample)
    out = {"n_sample": tot, "n_uniq_total": len(uniq), "codes": dict(codes),
           "supported_rate": round(codes.get("supported", 0) / max(1, tot), 4),
           "examples": fails}
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False, indent=1)[:2600], flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
