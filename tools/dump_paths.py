# -*- coding: utf-8 -*-
r"""把一次预测的台账还原成「反应路径」并打印/导出（命令行版）。

用法：
  python tools\dump_paths.py <输出目录或台账.csv>
  python tools\dump_paths.py <...> --smiles "C1=CC=CC=C1O"      # 只看某个产物
  python tools\dump_paths.py <...> --all -o paths.json          # 全部产物（含单跳）导出
  python tools\dump_paths.py <...> --all --csv paths.csv        # 导出成表（给文献对照用）

口径：一跳 = 台账一行 = 一个规则作用在一对底物上；一条链 = 从种子到目标的若干跳。
只读台账，不改数据、不排序、不加化学假设。
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

_ROOT = Path(__file__).resolve().parent.parent
for _sub in ("core", "conditions"):
    _p = str(_ROOT / _sub)
    if _p not in sys.path:
        sys.path.insert(0, _p)

import reaction_paths as rp  # noqa: E402


def _pick_csv(arg: str) -> Path:
    p = Path(arg)
    if p.is_file():
        return p
    csvs = sorted(p.glob("*.csv"))
    if not csvs:
        raise SystemExit("目录里没有 *.csv 台账：%s" % p)
    return csvs[-1]


def _labels(meta_path: Path, prod_formula: dict) -> dict:
    labels = dict(prod_formula)
    if meta_path.exists():
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        except Exception as ex:      # noqa: BLE001 —— 打印，不静默
            print("   [warn] meta 读不了：%s" % ex, file=sys.stderr)
            meta = {}
        for s in (meta.get("seeds") or []):
            nm, smi = str(s.get("name") or "").strip(), str(s.get("smiles") or "").strip()
            if nm and smi and nm != smi and not rp.looks_like_smiles(nm):
                labels[smi] = nm
    return labels


def main() -> int:
    ap = argparse.ArgumentParser(description="把台账还原成反应路径（只读）")
    ap.add_argument("path", help="输出目录，或直接给台账 CSV")
    ap.add_argument("--smiles", default="", help="只看某个产物的路径")
    ap.add_argument("--all", action="store_true", help="导出全部产物（含单跳）")
    ap.add_argument("--min-round", type=int, default=1, help="只导出至少这么多轮的产物（默认 1）")
    ap.add_argument("--max-chains", type=int, default=8, help="每个产物最多几条链（默认 8）")
    ap.add_argument("-o", "--json", default="", help="把结果写成 JSON")
    ap.add_argument("--csv", dest="csv_out", default="", help="把结果写成 CSV（产物 × 首选路径）")
    a = ap.parse_args()

    csv_path = _pick_csv(a.path)
    hops = rp.load_hops(csv_path)
    index = rp.build_index(hops)
    rule_names = rp.load_rule_names()
    prod_formula = {}
    src_name = {}
    for h in hops:
        if h.product and h.product_formula:
            prod_formula.setdefault(h.product, h.product_formula)
        if h.source and h.source_name:
            src_name.setdefault(h.source, h.source_name)
    meta_path = csv_path.with_suffix("").with_suffix(".meta.json")
    if not meta_path.exists():
        meta_path = csv_path.with_suffix(".meta.json")
    labels = _labels(meta_path, prod_formula)
    labels.update({k: v for k, v in src_name.items()
                   if k not in labels and v != k and not rp.looks_like_smiles(v)})
    # 还没有标签的分子（多半是 --smiles 输入的种子）：现算分子式，最多 60 个
    _need = [s for s in {h.source for h in hops} if s not in labels][:60]
    for _smi in _need:
        _f = rp.formula_of(_smi)
        if _f:
            labels[_smi] = _f

    print("台账：%s" % csv_path)
    print("跳数 %d · 产物 %d · 规则 %d 条有名" % (len(hops), len(index), len(rule_names)))

    def _rounds(smi):
        return max((int(float(h.round)) for h in index[smi] if h.round), default=0)

    targets = [a.smiles] if a.smiles else (
        sorted(index) if a.all else [s for s in index if _rounds(s) >= 2])
    if a.smiles and a.smiles not in index:
        # 允许用 InChIKey/分子式以外的任何前缀来找
        cand = [s for s in index if s.startswith(a.smiles)]
        targets = cand[:1]
        if not targets:
            print("错误：台账里没有这个产物（也没有以它开头的结构）", file=sys.stderr)
            return 2

    rows_out = []
    shown = 0
    for smi in targets:
        chs = rp.chains(smi, index, max_chains=a.max_chains)
        n_round = _rounds(smi)
        if not a.json and not a.csv_out:
            print("\n== %s%s · %d 跳 · %d 条链 =="
                  % (labels.get(smi, smi[:40]), ("（%s）" % prod_formula.get(smi, ""))
                     if prod_formula.get(smi) else "", n_round, len(chs)))
            for i, c in enumerate(chs, 1):
                print("  [%d] %s" % (i, rp.render_chain(c, rule_names, labels)))
            shown += 1
        for c in chs:
            rows_out.append({
                "product_smiles": smi,
                "product_formula": prod_formula.get(smi, ""),
                "rounds": n_round,
                "chain_len": len(c),
                "seed": labels.get(c[0].source, c[0].source),
                "rules": " > ".join(h.rule for h in c),
                "path_text": rp.render_chain(c, rule_names, labels),
            })
    if not shown and not a.json and not a.csv_out:
        print("没有 ≥2 跳的产物；用 --all 或 --smiles 看单跳产物。")

    if a.json:
        Path(a.json).write_text(json.dumps(rows_out, ensure_ascii=False, indent=1), encoding="utf-8")
        print("\n写出 %d 行 -> %s" % (len(rows_out), a.json))
    if a.csv_out:
        with open(a.csv_out, "w", encoding="utf-8-sig", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(rows_out[0].keys()) if rows_out else
                               ["product_smiles", "product_formula", "rounds", "chain_len",
                                "seed", "rules", "path_text"])
            w.writeheader()
            w.writerows(rows_out)
        print("\n写出 %d 行 -> %s" % (len(rows_out), a.csv_out))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
