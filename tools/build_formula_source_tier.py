# -*- coding: utf-8 -*-
r"""生成 ``data/formula_source_tier.json``（第七十五轮 H1 的产出文件）。

输入（**只读**，一个字节都不改）：
  * ``D:\TCMAI\data\formula_db.json``        —— 用户方剂库 6,743 名 / 12,071 条
  * ``D:\TCMAI\data\formula_db_api_only.json`` —— AI 现查那一批（用来对齐条数，5,332）
  * ``data/chp_formulas.json``               —— 药典成方制剂 overlay（1,526 方，全 tier 0）

输出：``data/formula_source_tier.json``

自带三条硬断言（不通过就退出码非 0）：
  1. 每条记录都有 tier（总数 == 12,071）；
  2. tier 5 的条数 == ``formula_db_api_only.json`` 的记录数（== 5,332）；
  3. 认不出的出处的条数 == 0（若哪天用户库新增了别的 chuchu 值，这里会**显式报错**，
     而不是猜一个档位塞进去）。
"""
from __future__ import annotations

import hashlib
import json
import sys
import time
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

STAGE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(STAGE / "sources"))

import formula_source as FS                                     # noqa: E402

FJ = Path(r"D:\TCMAI\data\formula_db.json")
API = Path(r"D:\TCMAI\data\formula_db_api_only.json")
CHP = STAGE / "data" / "chp_formulas.json"
OUT = STAGE / "data" / "formula_source_tier.json"


def sha256_of(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    db = json.loads(FJ.read_text(encoding="utf-8"))
    api = json.loads(API.read_text(encoding="utf-8"))
    chp = json.loads(CHP.read_text(encoding="utf-8"))

    tiers = {}
    srcs = {}
    counts = {str(t): 0 for t in FS.TIER_LABELS}
    unknown = []
    n_rec = 0
    tier5_claims = {}

    for nm, recs in db.items():
        tl, sl = [], []
        for i, r in enumerate(recs):
            n_rec += 1
            try:
                t = FS.tier_of_record(r)
            except ValueError as ex:
                unknown.append({"name": nm, "i": i, "why": str(ex)})
                continue
            tl.append(t)
            sl.append(str(r.get("chuchu") or ""))
            counts[str(t)] = counts.get(str(t), 0) + 1
            if t == FS.AI_TIER:
                s = str(r.get("chuchu") or "")
                if "药典" in s:
                    tier5_claims[s[:20]] = tier5_claims.get(s[:20], 0) + 1
        if tl:
            tiers[nm] = tl
            srcs[nm] = sl

    n_api = sum(len(v) for v in api.values())
    print("=" * 96)
    print("H1 · 方剂出处分档 —— 生成 data/formula_source_tier.json")
    print("=" * 96)
    print("  输入 formula_db.json：%d 个方名 / %d 条记录（sha256 %s…）"
          % (len(db), n_rec, sha256_of(FJ)[:12]))
    print("  对齐 formula_db_api_only.json：%d 条记录" % n_api)
    print()
    for t in sorted(FS.TIER_LABELS):
        print("   %-10s %6d 条" % (FS.tier_label(t), counts.get(str(t), 0)))
    print("   %-10s %6d 条" % ("合计", sum(int(v) for v in counts.values())))
    print()
    print("  tier 5 里「自称出处含药典」的（**只标注，不改档、不隐藏**）：")
    for k, v in sorted(tier5_claims.items(), key=lambda x: -x[1]):
        print("      %6d 条  自称 %s" % (v, k))

    ok = True
    if n_rec != 12071:
        print("  ★ 断言失败：记录总数 %d != 12,071（用户库变了？）" % n_rec)
        ok = False
    if counts[str(FS.AI_TIER)] != n_api:
        print("  ★ 断言失败：tier 5 = %d != api_only 记录数 %d"
              % (counts[str(FS.AI_TIER)], n_api))
        ok = False
    if unknown:
        print("  ★ 认不出的出处 %d 条（**不猜档位**），前 5 条：" % len(unknown))
        for u in unknown[:5]:
            print("      %s[%d] %s" % (u["name"], u["i"], u["why"]))
        ok = False

    art = {
        "schema": 1,
        "built_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "what": "方剂记录的出处可信度分层（药典 / ETCM / ITCM / CPMCP / 古籍 / AI 现查（未核对）；内部 code 0–5）",
        "rule": {
            "ai_batch": "category 字段缺失（== formula_db_api_only.json 那 5,332 条）→ 5",
            "by_chuchu": dict(FS.SRC_TIER),
            "note": "tier 是**来源**标签：AI 现查批自称哪本书都不改判；自称药典的条数见 tier5_selfclaim",
        },
        "source": {"path": str(FJ), "bytes": FJ.stat().st_size, "sha256": sha256_of(FJ)},
        "align": {"path": str(API), "n_records": n_api},
        "n_names": len(db),
        "n_records": n_rec,
        "tier_labels": {str(k): v for k, v in FS.TIER_LABELS.items()},
        "counts": counts,
        "tier5_selfclaim": tier5_claims,
        "unknown_src": unknown,
        # 顺序与 formula_db.json 里该方名的记录顺序一致
        "tiers": tiers,
        "srcs": srcs,
        # 药典 overlay：1,526 方全 tier 0（法定组成，来自药典原文）
        "chp_overlay": {k: 0 for k in chp},
    }
    OUT.write_text(json.dumps(art, ensure_ascii=False, separators=(",", ":")),
                   encoding="utf-8")
    print()
    print("  写出 %s（%.1f MB）%s"
          % (OUT, OUT.stat().st_size / 1e6, "" if ok else "  ★ 但有断言失败，见上"))
    return 0 if ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
