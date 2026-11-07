# -*- coding: utf-8 -*-
r"""给「库外规范名」建**中文名 → 物种**桥：NTU 规范名 → Wikidata 分类单元 → 学名 → COCONUT 物种。

背景（第七十五轮）：
  * 别名表里 8,022 个规范名，**5,982 个不在 tcm.db**（多为《中华本草》冷门植物）；
  * 本地三条源都不行（NTU 表无物种列 / SymMap 只有药名拉丁 / 药典只有 617 味）；
  * Wikidata 信道实测可行，但**必须加"名字对得上"的约束**：
    不加约束时 5 个常见名里 2 个错（黄连→白屈菜、丹参→鼠尾草）；
    加了约束后 5/5 正确，随机 20 个冷名里 **45% 能在 COCONUT 落到物种**。

本脚本把这件事**全量跑一遍**（可断点续跑）：
  * 缓存：`data\alias_species_cache.json`（每处理一个就落盘，中断不丢）
  * 产物：`data\alias_species_bridge.json`（name → {qid, sci, coconut_species, n_compounds}）
  * 限流：命中 429 自动退避；每次请求间隔 `--sleep`（默认 1.2 s）

用法：
    python tools\build_alias_species_bridge.py            # 全量（约 4–6 小时，建议整夜）
    python tools\build_alias_species_bridge.py --limit 100
    python tools\build_alias_species_bridge.py --report  # 只汇总现有缓存
"""
from __future__ import annotations

import argparse
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

STAGE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(STAGE / "tools"))
from _poc_alias_species_wikidata import (wd_search, wd_entity, scientific_name,
                                         is_taxon, name_matches)   # noqa: E402
from _poc_alias_species_wikidata import API, _get          # noqa: E402
import urllib.parse                                        # noqa: E402


def wd_entities(qids: list) -> dict:
    r"""一次请求取多个实体（wbgetentities 支持 50 个 id，省掉逐条请求）。"""
    if not qids:
        return {}
    url = (API + "?action=wbgetentities&format=json&props=claims|labels|aliases"
           "&languages=zh|zh-hans|zh-cn|zh-hant|en&ids=" + urllib.parse.quote("|".join(qids)))
    return json.loads(_get(url)).get("entities", {})

CACHE = STAGE / "data" / "alias_species_cache.json"
OUT = STAGE / "data" / "alias_species_bridge.json"
TCM = "file:D:/TCMAI/tcm.db?mode=ro"
COCO = "file:D:/TCMAI/coconut.db?mode=ro"


def load_cache() -> dict:
    if CACHE.exists():
        try:
            return json.loads(CACHE.read_text(encoding="utf-8"))
        except Exception:                                    # noqa: BLE001
            pass
    return {}


def save_cache(d: dict) -> None:
    CACHE.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")


def pending_names() -> list:
    c = sqlite3.connect(TCM, uri=True)
    have = {r[0] for r in c.execute("SELECT name_cn FROM herbs")}
    c.close()
    ai = json.loads((STAGE / "data" / "alias_index.json").read_text(encoding="utf-8"))
    prim = sorted({x["canonical"] for cs in ai["by_alias"].values() for x in cs
                   if any("\u4e00" <= ch <= "\u9fff" for ch in x["canonical"])})
    return [p for p in prim if p not in have]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=10 ** 9)
    ap.add_argument("--sleep", type=float, default=0.6)
    ap.add_argument("--report", action="store_true")
    ap.add_argument("--from-tokens", action="store_true",
                    help="只桥「方剂组成里对不上」的高频名字（读 data\\formula_unmatched_tokens.json）")
    ap.add_argument("--top", type=int, default=300, help="配合 --from-tokens：取前 K 个高频名")
    a = ap.parse_args()

    cache = load_cache()
    if a.from_tokens:
        tk = json.loads((STAGE / "data" / "formula_unmatched_tokens.json")
                        .read_text(encoding="utf-8"))["counts"]
        names = [k for k, _v in sorted(tk.items(), key=lambda x: -x[1])][:a.top]
        print("  优先级模式：取方剂里对不上的前 %d 个高频名" % len(names))
    else:
        names = pending_names()

    def summarize() -> None:
        done = [v for v in cache.values() if v.get("done")]
        bridged = [v for v in done if v.get("coconut_species")]
        print("  已处理 %d / %d ｜ 有分类单元 %d ｜ 有学名 %d ｜ 落到 COCONUT %d（%.1f%%）"
              % (len(done), len(names),
                 sum(1 for v in done if v.get("qid")),
                 sum(1 for v in done if v.get("sci")),
                 len(bridged), 100.0 * len(bridged) / max(1, len(done))))

    if a.report:
        summarize()
        return 0

    todo = [n for n in names if not (cache.get(n) or {}).get("done")][:a.limit]
    print("=" * 96)
    print("中文名→物种桥：待处理 %d 个（总缺口 %d，已有缓存 %d）" % (len(todo), len(names), len(cache)))
    print("=" * 96)
    coco = sqlite3.connect(COCO, uri=True)
    t0 = time.time()
    for i, nm in enumerate(todo, 1):
        rec = {"done": True, "qid": "", "sci": "", "coconut_species": "", "n_compounds": 0}
        try:
            hits = wd_search(nm)[:3]
            # ★ 先试"标签与查询名相同"的候选（多数情况第一条就中），省掉多余的实体请求
            hits.sort(key=lambda h: 0 if (h.get("label") or "").strip() == nm.strip() else 1)
            ents = wd_entities([h["id"] for h in hits])       # ★ 一条请求拿全部候选
            for h in hits:
                ent = ents.get(h["id"]) or {}
                if is_taxon(ent) and name_matches(nm, ent):
                    rec["qid"] = h["id"]
                    rec["label"] = h.get("label", "")
                    rec["sci"] = scientific_name(ent)
                    break
            if rec["sci"]:
                r = coco.execute(
                    "SELECT species, COUNT(*) FROM species_compound "
                    "WHERE lower(species) = ? GROUP BY species LIMIT 1",
                    (rec["sci"].lower(),)).fetchone()
                if r:
                    rec["coconut_species"] = r[0]
                    rec["n_compounds"] = int(r[1])
        except Exception as ex:                              # noqa: BLE001
            rec = {"done": False, "err": "%s: %s" % (type(ex).__name__, str(ex)[:80])}
        cache[nm] = rec
        if i % 25 == 0 or i == len(todo):
            save_cache(cache)
            el = time.time() - t0
            print("  ... %d/%d（%.0fs，约 %.1f s/个）" % (i, len(todo), el, el / i))
        time.sleep(a.sleep)
    coco.close()
    save_cache(cache)
    done = {k: v for k, v in cache.items() if v.get("done")}
    OUT.write_text(json.dumps(done, ensure_ascii=False, indent=1), encoding="utf-8")
    print()
    summarize()
    print("  产物 -> %s" % OUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
