# -*- coding: utf-8 -*-
r"""一次性 PoC：用 Wikidata 给「库外规范名」找物种学名，再接到 COCONUT。

链路：中文名 --Wikidata 搜索--> 分类单元实体 --P225(学名)--> 学名 --COCONUT--> 成分
只跑 `--n` 个名字（默认 20），用来估命中率；命中率够才值得全量跑。
"""
from __future__ import annotations

import argparse
import json
import re
import sqlite3
import sys
import time
import urllib.parse
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

STAGE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(STAGE / "tools"))
from h2_fetch import fetch                                # noqa: E402

API = "https://www.wikidata.org/w/api.php"


def wd_search(name: str) -> list:
    url = (API + "?action=wbsearchentities&format=json&language=zh&uselang=zh"
           "&limit=3&search=" + urllib.parse.quote(name))
    return (json.loads(_get(url)).get("search") or [])


def wd_entity(qid: str) -> dict:
    url = (API + "?action=wbgetentities&format=json&props=claims|labels|aliases"
           "&languages=zh|zh-hans|zh-cn|zh-hant|en&ids=" + qid)
    return json.loads(_get(url)).get("entities", {}).get(qid, {})


def _get(url: str, tries: int = 3) -> str:
    r"""带退避的 GET：命中 429（限流）就等一会再试。"""
    last = None
    for k in range(tries):
        try:
            return fetch(url, timeout=30)
        except Exception as ex:                             # noqa: BLE001
            last = ex
            if "429" in str(ex) and k + 1 < tries:
                time.sleep(8 * (k + 1))
                continue
            raise
    raise last if last else RuntimeError("unreachable")


def scientific_name(ent: dict) -> str:
    r"""P225 = taxon name（学名）。"""
    for c in ((ent.get("claims") or {}).get("P225") or []):
        try:
            return c["mainsnak"]["datavalue"]["value"]
        except Exception:                                   # noqa: BLE001
            continue
    return ""


def is_taxon(ent: dict) -> bool:
    r"""P105 = taxon rank（有它基本就是分类单元）。"""
    return bool(((ent.get("claims") or {}).get("P105")))


def zh_labels(ent: dict) -> set:
    """实体自己的中文标签与别名（用于"名字必须对得上"的约束）。"""
    out = set()
    for k in ("zh", "zh-hans", "zh-cn", "zh-hant"):
        v = ((ent.get("labels") or {}).get(k) or {}).get("value")
        if v:
            out.add(v.strip())
    for k in ("zh", "zh-hans"):
        for a in (((ent.get("aliases") or {}).get(k)) or []):
            v = a.get("value")
            if v:
                out.add(v.strip())
    return out


def name_matches(name: str, ent: dict) -> bool:
    r"""标签/别名里必须有与查询名**相同**的一项（去括号后比较）。"""
    want = {name, re.sub(r"[（(].*?[)）]", "", name).strip()}
    got = zh_labels(ent)
    return bool(want & got)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=20)
    ap.add_argument("--sleep", type=float, default=1.2)
    ap.add_argument("--random", action="store_true",
                    help="随机抽样（固定种子 20261016），避免按字典序取到一片同前缀名")
    ap.add_argument("--seed", type=int, default=20261016)
    a = ap.parse_args()

    c = sqlite3.connect("file:D:/TCMAI/tcm.db?mode=ro", uri=True)
    have = {r[0] for r in c.execute("SELECT name_cn FROM herbs")}
    c.close()
    ai = json.loads((STAGE / "data" / "alias_index.json").read_text(encoding="utf-8"))
    prim = sorted({x["canonical"] for cs in ai["by_alias"].values() for x in cs
                   if any("\u4e00" <= ch <= "\u9fff" for ch in x["canonical"])})
    miss = [p for p in prim if p not in have][:a.n]
    if a.random:
        import random
        rng = random.Random(a.seed)
        miss = rng.sample([p for p in prim if p not in have], a.n)

    coco = sqlite3.connect("file:D:/TCMAI/coconut.db?mode=ro", uri=True)
    n_taxon = n_name = n_coco = 0
    rows = []
    for i, nm in enumerate(miss, 1):
        got = {"name": nm}
        try:
            hits = wd_search(nm)
            qid = ""
            for h in hits[:3]:
                ent = wd_entity(h["id"])
                if is_taxon(ent) and name_matches(nm, ent):
                    qid = h["id"]
                    got["qid"] = qid
                    got["label"] = h.get("label", "")
                    sn = scientific_name(ent)
                    got["sci"] = sn
                    if sn:
                        n_name += 1
                    break
                time.sleep(0.3)
            if qid:
                n_taxon += 1
            if got.get("sci"):
                r = coco.execute("SELECT DISTINCT species FROM species_compound "
                                 "WHERE lower(species) LIKE ? LIMIT 1",
                                 ("%" + got["sci"].lower() + "%",)).fetchone()
                if r:
                    got["coconut"] = r[0]
                    n_coco += 1
        except Exception as ex:                              # noqa: BLE001
            got["err"] = "%s: %s" % (type(ex).__name__, ex)
        rows.append(got)
        print("  #%02d %-10s → qid=%-9s 学名=%-28s COCONUT=%s"
              % (i, nm, got.get("qid", "-"), (got.get("sci") or "-")[:28],
                 got.get("coconut") or "-"))
        time.sleep(a.sleep)
    coco.close()
    out = STAGE / "data" / "alias_species_poc.json"
    out.write_text(json.dumps({"n": len(miss), "taxon": n_taxon, "sci": n_name,
                               "coconut": n_coco, "rows": rows},
                              ensure_ascii=False, indent=1), encoding="utf-8")
    print()
    print("  %d 个里：找到分类单元 %d ｜ 拿到学名 %d ｜ COCONUT 里有物种 %d（%.0f%%）"
          % (len(miss), n_taxon, n_name, n_coco, 100.0 * n_coco / max(1, len(miss))))
    print("  -> %s" % out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
