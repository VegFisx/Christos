# -*- coding: utf-8 -*-
r"""建「中文药名 → 物种拉丁名」映射（从药典 2025 知识库抽取）。

为什么需要（用户 2026-10-16）：tcm.db 缺 52 味药典收载药材，其中 40 味现有规则已能
落到基原（制何首乌→何首乌…），真正缺 12 味；这 12 味里有 8 味能在 COCONUT 找到物种
（杠板归 → polygonum perfoliatum …）。药典正文写的是「本品为蓼科植物[[杠板归]]
Polygonum perfoliatum L. 的干燥地上部分。」—— 拉丁学名**不带【来源】小标题**，
直接写在正文里（第一版按标题找，实测 0 命中，已修）。

输出 ``data/herb_species.json``：中文药名 → {latin_raw, species, source, url}。
用法：``python tools/build_herb_species.py``
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
sys.path.insert(0, str(STAGE / "sources"))
Z = STAGE / "reports" / "_probe_net" / "indkb.zip"
SUB = "一部/药材和饮片/"
OUT = STAGE / "data" / "herb_species.json"

BINOM = re.compile(r"\b([A-Z][a-z]{3,})\s+([a-z]{4,})\b")
STOP = {"radix", "rhizoma", "folium", "herba", "cortex", "fructus", "semen",
        "flos", "lignum", "resina", "caulis", "ramulus"}


def main() -> int:
    import coconut as CC
    z = zipfile.ZipFile(Z)
    md = [i.filename for i in z.infolist()
          if i.filename.endswith(".md") and SUB in i.filename]
    out = {}
    n_lat = n_hit = n_nolat = 0
    for fn in md:
        name = Path(fn).stem
        t = z.read(fn).decode("utf-8", "replace")
        if "内容获取失败" in t:
            continue
        head = re.sub(r"\s+", " ", t)[:600]
        raws, sps = [], []
        for m in BINOM.finditer(head):
            g, s = m.group(1), m.group(2)
            if s.lower() in STOP:
                continue
            raw = m.group(0)
            if raw in raws:
                continue
            raws.append(raw)
            hit, _how = CC.looks_like_species(raw)
            if hit and hit not in sps:
                sps.append(hit)
        if raws:
            n_lat += 1
            if sps:
                n_hit += 1
        else:
            n_nolat += 1
        if raws or sps:
            url = re.search(r'url:\s*"([^"]*)"', t)
            out[name] = {"latin_raw": raws[:4], "species": sps[:4],
                         "source": "中国药典2025版一部",
                         "url": url.group(1) if url else ""}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print("药典药材条目 = %d" % len(md))
    print("  能抓到拉丁学名 = %d ｜ 其中在 COCONUT 命中物种 = %d ｜ 抓不到 = %d"
          % (n_lat, n_hit, n_nolat))
    print("  已写出 -> %s（%.2f MB，%d 条）"
          % (OUT, OUT.stat().st_size / 1048576, len(out)))
    print("\n抽样：")
    for k in list(out)[:5] + ["杠板归", "蓝布正", "瓜子金"]:
        if k in out:
            print("   %-10s %s → %s"
                  % (k, out[k]["latin_raw"][:2], out[k]["species"][:2]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
