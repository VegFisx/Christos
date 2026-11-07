# -*- coding: utf-8 -*-
r"""D3 受限池问答：只用你给的这批底物，能不能做出目标分子？

把逆合成的「可获得集合」整个换成你给的池子 -> 每条路线的终点必须落在池内。
现有 retro_search 只回答「从任意可获得集合能不能到目标」，对「我用这些底物行不行」是答非所问。

用法:
  python tools/pool_query.py --herb 甘草 --limit 12 --list
  python tools/pool_query.py --pool-csv reports/query_inventory_paths.csv --col source_smiles --target "CC(=O)Oc1ccccc1C(=O)O" --depth 2
  python tools/pool_query.py --smiles-file pool.txt --target <smiles>

注意：--herb 会读 tcm.db（走项目自己的 sources/herb.py，只读）。爬虫运行期间建议用 --pool-csv / --smiles-file。
"""
from __future__ import annotations

import argparse
import csv
import sys
import time
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

_STAGE = Path(__file__).resolve().parent.parent
for _p in (_STAGE / "core", _STAGE / "rules", _STAGE / "libs", _STAGE / "tools",
           _STAGE / "sources", _STAGE / "conditions"):
    if _p.is_dir() and str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from rdkit import Chem, RDLogger                                  # noqa: E402
from rdkit.Chem import Descriptors, rdMolDescriptors             # noqa: E402
import retro_search as rs                                        # noqa: E402

RDLogger.DisableLog("rdApp.*")
TAB = chr(9)


def pool_from_herb(name, limit):
    from herb import compounds_of_herb
    out = []
    for h in [x.strip() for x in str(name).split(",") if x.strip()]:
        for c in compounds_of_herb(h, limit=limit):
            out.append((str(getattr(c, "name", "") or h), str(getattr(c, "smiles", "") or "")))
    return out


def pool_from_csv(path, col):
    out = []
    with open(path, encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            v = str(row.get(col) or "").strip()
            if v:
                nm = str(row.get("source_name") or "")[:24] or col
                out.append((nm, v))
    return out


def pool_from_file(path):
    out = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split(TAB)
        out.append((parts[0].strip(), parts[1].strip()) if len(parts) >= 2 else (line[:24], line))
    return out


def main():
    ap = argparse.ArgumentParser(description="D3 受限池问答")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--herb", default=None)
    g.add_argument("--pool-csv", default=None)
    g.add_argument("--smiles-file", default=None)
    ap.add_argument("--col", default="source_smiles")
    ap.add_argument("--limit", type=int, default=15)
    ap.add_argument("--target", default=None)
    ap.add_argument("--depth", type=int, default=2)
    ap.add_argument("--beam", type=int, default=4)
    ap.add_argument("--list", action="store_true")
    # ★ D7（2026-10-13）：只显示「化学可用」的路线。默认关（不改既有行为）；
    #   背景：实测端到端化学可用率 41%（reports/B-搜索层过滤-报告.md），
    #   不可用路线仍会被返回并标注原因（R1_残基/R2_前体大于目标/R3_惰性小分子/R4_荒谬前体）。
    ap.add_argument("--usable-only", action="store_true",
                    help="只显示 usable=True 的路线（默认关：不可用路线照常返回并标注原因）")
    # ★ D7（2026-10-14）：逆模板黑名单（默认关）——体检出的 54 条「never usable」模板，
    #   打开后本次搜索不再用它们（只影响本次；模板库文件一个字不动；台账会标注开/关）。
    ap.add_argument("--retro-blacklist", action="store_true",
                    help="启用 never-usable 逆模板黑名单（默认关；来源 reports/retro_template_blacklist.json）")
    a = ap.parse_args()

    if a.herb:
        pool, desc = pool_from_herb(a.herb, a.limit), "药材 " + a.herb + "（tcm.db）"
    elif a.pool_csv:
        pool, desc = pool_from_csv(a.pool_csv, a.col), "台账 " + a.pool_csv + " 列 " + a.col
    else:
        pool, desc = pool_from_file(a.smiles_file), "文件 " + a.smiles_file

    avail, bad, seen = {}, 0, set()
    for nm, smi in pool:
        m = Chem.MolFromSmiles(str(smi or ""))
        if m is None:
            bad += 1
            continue
        cs = Chem.MolToSmiles(m)
        if cs in seen:
            continue
        seen.add(cs)
        try:
            k = Chem.MolToInchiKey(m)
        except Exception:
            bad += 1
            continue
        if k and k not in avail:
            avail[k] = "pool:" + str(nm or "?")

    print("=" * 84)
    print("D3 受限池问答")
    print("=" * 84)
    print("池子来源：" + desc)
    print("池子：输入 %d 条 -> 去重后 %d 个分子（解析失败 %d）" % (len(pool), len(avail), bad))
    if a.list:
        for nm, smi in pool[:60]:
            print("   " + str(nm)[:28].ljust(28) + " " + str(smi)[:60])
    if not avail:
        print("池子是空的。")
        return 2
    if not a.target:
        print("")
        print("没给 --target：只列池子。要问「这批底物能不能做出 X」，加 --target <SMILES>。")
        return 0

    tm = Chem.MolFromSmiles(a.target)
    if tm is None:
        print("目标 SMILES 解析失败：" + a.target)
        return 2
    tgt = Chem.MolToSmiles(tm)
    print("")
    print("目标：" + tgt + "  (%s, MW %.1f)" % (rdMolDescriptors.CalcMolFormula(tm), Descriptors.MolWt(tm)))
    print("搜索：depth<=%d, beam=%d；终止集合 = 只有这个池子（不含 COCONUT / 可购砌块）" % (a.depth, a.beam))
    print("")

    templates = rs.load_rdchiral_templates()
    bl_info = {"enabled": False, "n_dropped": 0}
    if a.retro_blacklist:
        templates, bl_info = rs.apply_retro_blacklist(templates, verbose=True)
    print("逆模板：%d 条 · 黑名单（D7）：%s"
          % (len(templates), ("开 -> 丢弃 %d 条" % bl_info.get("n_dropped", 0))
             if bl_info.get("enabled") else "关（默认）"))
    eng = rs.RetroSearch(templates, avail, blocks_full={}, blocks_skel={})
    routes, stat = eng.search(tgt, max_depth=a.depth, beam=a.beam)
    print("统计：" + str(stat))
    # ★ D7：台账标注 —— 本次查询用了哪套模板（黑名单开/关），写进 query_log（只记录，不影响结果）
    try:
        import query_base as qb
        qb.dump_query_log([{
            "ts": time.strftime("%Y-%m-%d %H:%M:%S"), "cmd": "pool_query",
            "query": tgt, "resolved_kind": "smiles", "found": bool(routes),
            "n_hits": len(routes), "depth": a.depth, "beam": a.beam,
            "usable_only": bool(a.usable_only),
            "retro_blacklist": ("on:%d" % bl_info.get("n_dropped", 0))
                               if bl_info.get("enabled") else "off",
        }])
        print("query_log：已标注本次（cmd=pool_query，retro_blacklist=%s，黑名单与产物都不受影响）"
              % ("on" if bl_info.get("enabled") else "off"))
    except Exception as ex:                      # noqa: BLE001 —— 打印，不静默
        print(f"  [warn] query_log 写入失败：{type(ex).__name__}: {ex}")
    if a.usable_only:
        n0 = len(routes)
        routes = [r for r in routes if getattr(r, "usable", True)]
        print("★ --usable-only：%d 条 -> 只留可用 %d 条" % (n0, len(routes)))
    if not routes:
        print("")
        print("结论：在这批底物里没找到到目标的路线（受限池口径）。")
        print("注意：这只说明「当前逆模板 + 当前深度」下没有，不等于化学上不可能。")
        return 0
    for i, rt in enumerate(routes[:3], 1):
        print("")
        print("路线 %d（%d 步） 可用=%s 原因=%s" % (i, len(rt.steps), rt.usable, rt.unusable_reason))
        for j, st in enumerate(rt.steps, 1):
            tags = [p + ("[在池内]" if eng.is_available(p) else "[不在池内]") for p in st.precursors]
            print("   %d. [%s]" % (j, st.reaction_name))
            print("      目标 " + st.target[:64])
            print("      前体 " + " | ".join(tags))
        print("      终点（落在池内的）：" + str(rt.terminals))
    print("")
    print("★ 只回答「这批底物行不行」；不排序、不删产物、不给产率（打分已停工）。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
