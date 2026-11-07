# -*- coding: utf-8 -*-
r"""独立复核 DSH 的 gold 核对（第七十一轮）——**严格匹配器**对照。

差异点（只此一处，其余口径照抄以便对齐）：
  DSH 版：数值命中 = 全文任意位置出现等值数字（宽松；可能被别处同名数字"碰瓷"）。
  本版：数值必须出现在**标记名出现位置的 ±120 字窗口**内（严格）。
同一样本（同 csv、同去重、同种子 20261015、n=400），输出两类判定与不一致清单。
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
OUT = STAGE / "reports" / "chp_markers_2025" / "gold_check_crosscheck.json"


def strip_wikilinks(t: str) -> str:
    t = t.replace("［［", "[[").replace("］］", "]]").replace("［", "[").replace("］", "]")
    prev = None
    while prev != t:
        prev = t
        t = re.sub(r"\[\[([^\[\]|]*)\|([^\[\]]*)\]\]", r"\2", t)
        t = re.sub(r"\[\[([^\[\]]*)\]\]", r"\1", t)
    return t


def numbers(s: str):
    return [float(m.group(1)) for m in re.finditer(r"([0-9]+(?:\.[0-9]+)?)", s)]


def main() -> int:
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 400
    rows = list(csv.DictReader(open(CSV, encoding="utf-8-sig", newline="")))
    seen, uniq = set(), []
    for r in rows:
        key = (r.get("herb", ""), r.get("name", ""), r.get("value", ""),
               r.get("unit", ""), r.get("relation", ""))
        if key in seen:
            continue
        seen.add(key)
        uniq.append(r)
    sample = random.Random(20261015).sample(uniq, min(n, len(uniq)))
    zf = zipfile.ZipFile(ZIP)
    idx = {}
    for nm in zf.namelist():
        if nm.lower().endswith(".md"):
            idx.setdefault(nm.rsplit("/", 1)[-1][:-3], nm)

    codes_loose = Counter()
    codes_strict = Counter()
    disagreements = []
    for r in sample:
        herb = (r.get("herb") or "").strip()
        name = (r.get("name") or "").strip()
        val = (r.get("value") or "").strip()
        unit = (r.get("unit") or "").strip()
        p = idx.get(herb)
        if p is None:
            codes_loose["entry_missing"] += 1
            codes_strict["entry_missing"] += 1
            continue
        text = strip_wikilinks(zf.read(p).decode("utf-8", errors="replace"))
        text_sq = re.sub(r"\s+", "", text)
        name_sq = re.sub(r"\s+", "", name)
        hit_name = ((name in text) or (name_sq and name_sq in text_sq)) if name else None
        # ---- 宽松（= DSH 口径） ----
        v = None
        try:
            v = float(val) if val else None
        except ValueError:
            v = None
        if v is None:
            hit_loose = None
        else:
            hit_loose = any(abs(x - v) < 1e-9 for x in numbers(text))
        # ---- 严格：数值须落在"名称出现处"的 ±120 字窗口内 ----
        hit_strict = None
        if v is not None and name_sq:
            hit_strict = False
            for m in re.finditer(re.escape(name_sq), text_sq):
                win = text_sq[max(0, m.start() - 30): m.end() + 120]
                if any(abs(x - v) < 1e-9 for x in numbers(win)):
                    hit_strict = True
                    break
        is_sec = bool(re.match(r"^〔.*〕$", name)) if name else False
        for code, (_hn, hv) in (("loose", (hit_name, hit_loose)),
                                ("strict", (hit_name, hit_strict))):
            tgt = codes_loose if code == "loose" else codes_strict
            if is_sec:
                tgt["artifact_section_label"] += 1
            elif hit_name is False:
                tgt["name_missing"] += 1
            elif hv is False:
                tgt["value_missing"] += 1
            else:
                tgt["supported"] += 1
        if (not is_sec) and (hit_name is not False) and (hit_loose is True) and (hit_strict is False):
            i = text_sq.find(name_sq)
            disagreements.append({"herb": herb, "name": name, "val": val + unit,
                                   "ctx": text[max(0, i - 20): i + 90]})

    tot = len(sample)
    out = {"n": tot,
           "supported_rate_loose": round(codes_loose.get("supported", 0) / max(1, tot), 4),
           "supported_rate_strict": round(codes_strict.get("supported", 0) / max(1, tot), 4),
           "codes_loose": dict(codes_loose), "codes_strict": dict(codes_strict),
           "loose_only_examples": disagreements[:10]}
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({k: out[k] for k in ("n", "supported_rate_loose",
                                          "supported_rate_strict", "codes_strict")},
                     ensure_ascii=False, indent=1))
    print("宽松判支持、严格判不支持的例子数:", len(disagreements))
    for d0 in disagreements[:4]:
        print("  -", d0["herb"], "|", d0["name"], d0["val"], "| ctx:", d0["ctx"][:70])
    return 0


if __name__ == "__main__":
    sys.exit(main())
