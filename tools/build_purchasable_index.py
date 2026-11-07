# -*- coding: utf-8 -*-
r"""把可购砌块集合打包成【逆合成终端集合】索引。

输入 : reports\purchasable_blocks_core.tsv（核心砌块）
       reports\purchasable_blocks_reagents.tsv（试剂，可选，用 --with-reagents 纳入）
输出 : reports\purchasable_blocks_index.jsonl   每行 JSON，key = full InChIKey
       reports\purchasable_blocks_skeleton.jsonl  每行 JSON，key = InChIKey 前段(骨架)
       reports\purchasable_blocks_index_meta.json

为什么要两套索引：
  retro_search 现在用 is_available() 查 InChIKey。砌块里有相当一部分是
  【未定构型】的（ORD 里反应物常常没标立体），而产物侧有明确构型，
  只按 full InChIKey 查会漏。骨架索引做回退，并标注 match_level，
  由调用方决定要不要接受"骨架命中"。

用法:
  python build_purchasable_index.py                 # 只用核心砌块
  python build_purchasable_index.py --with-reagents # 连试剂一起（终端集合更宽）
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from collections import Counter
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

STAGE = Path(r"D:\ProgramData\DSHNS\chemreact-staging")
sys.path.insert(0, str(STAGE / "tools"))
sys.path.insert(0, str(STAGE / "libs"))
sys.path.insert(0, r"D:\TCMAI\src")

from rdkit import Chem, RDLogger  # noqa: E402
from rdkit.Chem import Descriptors  # noqa: E402

RDLogger.DisableLog("rdApp.*")
REPORTS = STAGE / "reports"
CORE = REPORTS / "purchasable_blocks_core.tsv"
REAG = REPORTS / "purchasable_blocks_reagents.tsv"
OUT_FULL = REPORTS / "purchasable_blocks_index.jsonl"
OUT_SKEL = REPORTS / "purchasable_blocks_skeleton.jsonl"
OUT_META = REPORTS / "purchasable_blocks_index_meta.json"
COCO = REPORTS / "coconut_inchikey_index.jsonl"
FIELDS = ["smiles", "inchikey_skeleton", "inchikey", "MW", "heavy_atoms", "formula",
          "n_as_reactant", "n_mapped_as_reactant", "map_ratio"]


def load(path, source):
    out = []
    if not path.exists():
        return out
    with open(path, encoding="utf-8") as f:
        for line in f:
            if line.startswith("#") or line.startswith("smiles\t"):
                continue
            p = line.rstrip("\n").split("\t")
            if len(p) != len(FIELDS):
                continue
            d = dict(zip(FIELDS, p))
            d["source"] = source
            out.append(d)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--core-only", action="store_true",
                    help="索引里只放核心砌块（默认放全部，靠 source 字段区分）")
    args = ap.parse_args()
    t0 = time.time()

    core = load(CORE, "ORD_core_block")
    # ★ 索引里【总是】包含试剂，靠 source 字段区分：
    #   这样 retrofit 的 load_purchasable_blocks(with_reagents=True) 才有东西可筛。
    #   （原来的写法是索引里只放核心砌块 -> with_reagents 完全无效，实测宽窄两版一样大）
    reag = load(REAG, "ORD_reagent")
    rows = core + reag
    print("=" * 88)
    print("可购砌块 -> 逆合成终端集合索引")
    print("=" * 88)
    print(f"  核心砌块 {len(core):,}" + (f" + 试剂 {len(reag):,}" if reag else "（未纳入试剂）"))
    print("  过滤说明：load_purchasable_blocks(with_reagents=False) 只取 ORD_core_block")

    # full InChIKey 去重（同一 key 保留出现次数最高、映射率最高的那个）
    def better(a, b):
        return (int(b["n_as_reactant"]), float(b["map_ratio"])) > \
               (int(a["n_as_reactant"]), float(a["map_ratio"]))

    by_full, by_skel = {}, {}
    n_no_ik = 0
    for r in rows:
        if not r["inchikey"]:
            n_no_ik += 1
            continue
        k, sk = r["inchikey"], r["inchikey_skeleton"]
        if k not in by_full or better(r, by_full[k]):
            by_full[k] = r
        if sk not in by_skel or better(r, by_skel[sk]):
            by_skel[sk] = r
        elif sk in by_skel and r["smiles"] != by_skel[sk]["smiles"]:
            by_skel[sk]["_n_stereo_variants"] = by_skel[sk].get("_n_stereo_variants", 0) + 1

    def dump(path, mapping, keyname):
        with open(path, "w", encoding="utf-8") as f:
            for k, r in mapping.items():
                _m = Chem.MolFromSmiles(r["smiles"])
                rec = {
                    keyname: k,
                    "smiles": r["smiles"],
                    "inchikey": r["inchikey"],
                    "formula": r["formula"],
                    "MW": float(r["MW"]),
                    "heavy_atoms": int(r["heavy_atoms"]),
                    "charge": Chem.GetFormalCharge(_m) if _m else 0,
                    "n_as_reactant": int(r["n_as_reactant"]),
                    "n_mapped_as_reactant": int(r["n_mapped_as_reactant"]),
                    "map_ratio": float(r["map_ratio"]),
                    "source": r["source"],
                }
                if keyname == "skeleton" and "_n_stereo_variants" in r:
                    rec["n_other_stereo_variants"] = r["_n_stereo_variants"]
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    dump(OUT_FULL, by_full, "inchikey")
    dump(OUT_SKEL, by_skel, "skeleton")
    print(f"  full InChIKey 索引 {len(by_full):,}  -> {OUT_FULL.name}"
          f"  ({OUT_FULL.stat().st_size/1024**2:.1f} MB)")
    print(f"  骨架索引        {len(by_skel):,}  -> {OUT_SKEL.name}"
          f"  ({OUT_SKEL.stat().st_size/1024**2:.1f} MB)")
    if n_no_ik:
        print(f"  [warn] {n_no_ik} 个砌块没有 InChIKey（RDKit InChI 挂死或无法解析），未入索引")

    # ---------- 与 COCONUT/tcm.db 的重叠：回答"新砌块比天然产物多了什么" ----------
    coco_keys = set()
    if COCO.exists():
        with open(COCO, encoding="utf-8") as f:
            for line in f:
                k = line.split("\t", 1)[0].strip()
                if k:
                    coco_keys.add(k)
    tcm_keys = set()
    try:
        from tcm_ro import use_readonly; use_readonly()
        from db_utils import open_db
        with open_db() as conn:
            for (k,) in conn.cursor().execute(
                    "SELECT inchi_key FROM compounds WHERE inchi_key IS NOT NULL AND inchi_key != ''"):
                tcm_keys.add(k)
    except Exception as ex:
        print(f"  [warn] tcm.db 读取失败: {ex}")
    old = coco_keys | tcm_keys
    new_keys = set(by_full) - old
    print()
    print(f"  旧终端集合（COCONUT+tcm.db）{len(old):,}")
    print(f"  砌块集合                     {len(by_full):,}")
    print(f"  ★ 砌块里【旧集合没有的】      {len(new_keys):,}"
          f"  ({len(new_keys)/max(len(by_full),1)*100:.1f}%)")

    # 分子量分布
    mws = sorted(float(r["MW"]) for r in by_full.values())
    def q(p):
        return mws[min(int(len(mws) * p), len(mws) - 1)] if mws else 0
    print()
    print("  砌块分子量分布: "
          f"min {mws[0]:.0f} / P25 {q(.25):.0f} / 中位 {q(.5):.0f} / "
          f"P75 {q(.75):.0f} / P95 {q(.95):.0f} / max {mws[-1]:.0f}")
    print(f"  MW<=300 的占 {sum(1 for m in mws if m <= 300)/max(len(mws),1)*100:.1f}%"
          f"   MW<=200 的占 {sum(1 for m in mws if m <= 200)/max(len(mws),1)*100:.1f}%")

    metas = {
        "n_core_blocks": len(core),
        "n_reagents_included": len(reag),
        "n_full_index": len(by_full),
        "n_skeleton_index": len(by_skel),
        "n_no_inchikey": n_no_ik,
        "n_not_in_old_terminal_set": len(new_keys),
        "n_old_terminal_set": len(old),
        "match_levels": {"full_inchikey": "chemically identical",
                         "skeleton": "same skeleton, stereo may differ"},
        "mw_median": q(.5),
        "elapsed_sec": round(time.time() - t0, 1),
    }
    OUT_META.write_text(json.dumps(metas, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n  -> {OUT_META.name}")
    print(f"耗时 {time.time()-t0:.1f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
