"""整味药自组方验证：把一个药材的**成分表**整批当底物起跑，看文献标记物是否出现。

种子来源与生产一致：直接调 `sources/herb.py::compounds_of_herb`（默认顺序＝marker 优先、
其次分子量降序、按结构去重），因此结果可以直接对应「用户不传任何开关时看到的东西」。

用法：
    python -I tools/validate_whole_herb.py --top 12
    python -I tools/validate_whole_herb.py --top 12 --include-precursors
    python -I tools/validate_whole_herb.py --top 12 --herb-order ob   # 旧口径：按 OB 降序

输出 reports/whole_herb_<tag>_20261106.json
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parent
for _sub in ("core", "conditions", "sources", "tools"):
    _p = str(_ROOT / _sub)
    if _p not in sys.path:
        sys.path.insert(0, _p)

import validate_formula_decoction as F  # noqa: E402
from herb import compounds_of_herb  # noqa: E402

# 药材 -> 标记物与前体（id 全部来自 tcm.db，不手写结构）
CASES = {
    "甘草": {
        "target_id": "HBIN028184", "target_name": "甘草次酸 glycyrrhetinic acid",
        "precursors": [("HBIN028191", "甘草酸 glycyrrhizin"),
                       ("HBIN033383", "甘草苷 liquiritin")],
    },
    "人参": {
        "target_id": "HBIN003457", "target_name": "人参皂苷 Rg3",
        "precursors": [("HBIN027729", "人参皂苷 Rb1 ginsenoside Rb1")],
    },
    "附子": {
        "target_id": "HBIN017810", "target_name": "苯甲酰乌头原碱 benzoylaconine",
        "precursors": [("HBIN014582", "乌头碱 aconitine"),
                       ("HBIN034775", "中乌头碱 mesaconitine"),
                       ("HBIN029816", "次乌头碱 hypaconitine")],
    },
}


def rank_of(full, iid: str) -> int:
    for k, c in enumerate(full):
        if getattr(c, "_iid", "") == iid:
            return k + 1
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--top", type=int, default=12)
    ap.add_argument("--max-pairs", type=int, default=400)
    ap.add_argument("--herb-order", default="marker", choices=["marker", "ob"])
    ap.add_argument("--include-precursors", action="store_true")
    args = ap.parse_args()

    con = F.db()
    out = {"generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
           "protocol": {
               "condition": "煎煮", "rounds": 1, "max_pairs": args.max_pairs,
               "seed_source": "sources/herb.py::compounds_of_herb（与生产同一函数）",
               "herb_order": args.herb_order,
               "order_note": ("marker 优先 → 分子量降序 → 按结构去重"
                              if args.herb_order == "marker"
                              else "TCMSP OB 降序（--herb-order ob 口径）"),
               "top_n": args.top,
               "include_precursors": bool(args.include_precursors)},
           "cases": {}}

    for herb, cfg in CASES.items():
        cs = compounds_of_herb(herb, limit=args.top,
                               order_tcmsp=(args.herb_order == "ob"))
        full = compounds_of_herb(herb, limit=10 ** 6,
                                 order_tcmsp=(args.herb_order == "ob"))

        seeds = [{"name": c.name or getattr(c, "_iid", "?"), "smiles": c.smiles,
                  "herb": herb} for c in cs if getattr(c, "smiles", "")]
        prec = [{"id": pid, "name": pname, "rank": rank_of(full, pid),
                 "in_seeds": any(getattr(c, "_iid", "") == pid for c in cs)}
                for pid, pname in cfg["precursors"]]

        if args.include_precursors:
            have = {getattr(c, "_iid", "") for c in cs}
            for pid, pname in cfg["precursors"]:
                if pid in have:
                    continue
                row = con.execute("SELECT ingredient_id, name_en, smiles FROM compounds "
                                  "WHERE ingredient_id = ?", (pid,)).fetchone()
                if row and row[2]:
                    seeds.append({"name": row[1] or pid, "smiles": row[2], "herb": herb})

        hops, secs = F.run_batch(seeds, "煎煮", max_pairs=args.max_pairs, rounds=1)
        hit = F.find_direct(con, hops, cfg["target_id"],
                            ("hydrolysis_glycoside", "hydrolysis_ester", "hydrolysis"))
        out["cases"][herb] = {
            "n_components_with_structure": len(full),
            "n_seeds_used": len(seeds),
            "seeds": [s["name"] for s in seeds],
            "precursors": prec,
            "seconds": secs, "n_hops": len(hops),
            "target": cfg["target_name"],
            "target_status": (hit or {}).get("status", "not_found"),
            "target_rule": (hit or {}).get("rule", "-"),
            "target_round": (hit or {}).get("round", "-"),
        }
        print(f"== {herb} == 有结构成分 {len(full)}；种子 {len(seeds)}；"
              f"一轮 {len(hops)} 跳 / {secs}s → {out['cases'][herb]['target_status']}")
        print(f"   前体排名（本次排序口径）："
              f"{[(p['name'].split()[0], p['rank'], p['in_seeds']) for p in prec]}")

    tag = f"top{args.top}" + ("_prec" if args.include_precursors else "") + f"_{args.herb_order}"
    dst = _ROOT / "reports" / f"whole_herb_{tag}_20261106.json"
    dst.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"写出 {dst}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
