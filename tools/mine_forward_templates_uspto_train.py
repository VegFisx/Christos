# -*- coding: utf-8 -*-
"""从 USPTO-50k mapped 的**训练半区**挖正向模板（反应级排除官方 test）。

口径（写死）：
  1. 官方 test = reports/paper/data/uspto50k_official/raw_test.csv；
     其 signature = (规范化底物集合, 规范化产物集合)，忽略试剂。
  2. 训练池 = uspto50k_mapped.jsonl 中 signature **不在** test 里的行。
     这是反应级排除，不依赖专利 id（id 会重复）。
  3. 每条训练反应用 RDChiral 抽 retro 模板，翻成 forward（底物>>产物），
     support = 该 forward 模板在训练池里出现的次数。
  4. 输出 reports/mined_forward_templates_uspto_train.jsonl：
     {"template": ..., "support": n, "src": "uspto50k_train_excl_official_test"}

用法：
  python -I tools\\mine_forward_templates_uspto_train.py
  python -I tools\\mine_forward_templates_uspto_train.py --limit 2000   # 冒烟
"""
from __future__ import annotations

import argparse
import collections
import csv
import json
import re
import sys
import time
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

ROOT = Path(__file__).resolve().parents[1]
for _p in (ROOT / "libs", ROOT / "tools", ROOT / "core"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from rdkit import Chem, RDLogger  # noqa: E402
from rdchiral.template_extractor import extract_from_reaction  # noqa: E402

RDLogger.DisableLog("rdApp.*")

TEST = ROOT / "reports" / "paper" / "data" / "uspto50k_official" / "raw_test.csv"
MAPPED = ROOT / "reports" / "paper" / "data" / "uspto50k_mapped.jsonl"
OUT = ROOT / "reports" / "mined_forward_templates_uspto_train.jsonl"

_MAP = re.compile(r"\[([^:\]]*):\d+\]")


def strip_map(s: str) -> str:
    return _MAP.sub(r"[\1]", s or "")


def canon(s: str) -> str:
    m = Chem.MolFromSmiles(s) if s else None
    return Chem.MolToSmiles(m) if m is not None else ""


def split_rxn(rxn: str):
    parts = (rxn or "").split(">")
    if len(parts) == 3:
        return parts[0], parts[1], parts[2]
    if len(parts) == 2:
        return parts[0], "", parts[1]
    return "", "", ""


def sig_of(rxn: str):
    left, _mid, right = split_rxn(rxn)
    rs = frozenset(c for c in (canon(strip_map(x)) for x in left.split(".")) if c)
    ps = frozenset(c for c in (canon(strip_map(x)) for x in right.split(".")) if c)
    return (rs, ps)


def load_test_sigs() -> set:
    out = set()
    with open(TEST, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            out.add(sig_of(row["reactants>reagents>production"]))
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0, help="只处理前 N 条训练行（冒烟）")
    a = ap.parse_args()
    t0 = time.time()

    print("读取官方 test signature ...", flush=True)
    test_sigs = load_test_sigs()
    print("  test 唯一 signature %d（%.1fs）" % (len(test_sigs), time.time() - t0), flush=True)

    cnt: collections.Counter = collections.Counter()
    n_rows = n_test = n_ok = n_fail = 0
    for line in open(MAPPED, encoding="utf-8"):
        n_rows += 1
        d = json.loads(line)
        rxn = d.get("mapped_rxn") or ""
        if ">>" not in rxn and rxn.count(">") != 2:
            n_fail += 1
            continue
        if sig_of(rxn) in test_sigs:
            n_test += 1
            continue
        if a.limit and n_ok >= a.limit:
            break
        left, _mid, right = split_rxn(rxn)
        try:
            res = extract_from_reaction({"reactants": left, "products": right,
                                         "agents": "", "_id": str(n_rows)})
            tpl = (res or {}).get("reaction_smarts") or ""
        except Exception:
            tpl = ""
        if ">>" not in tpl:
            n_fail += 1
            continue
        retro_left, retro_right = tpl.split(">>", 1)
        cnt[retro_right + ">>" + retro_left] += 1
        n_ok += 1
        if n_ok % 5000 == 0:
            print("  ... 训练 %d · 唯一模板 %d · %.0fs"
                  % (n_ok, len(cnt), time.time() - t0), flush=True)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        for t, n in cnt.most_common():
            f.write(json.dumps({"template": t, "support": n,
                                "src": "uspto50k_train_excl_official_test"},
                               ensure_ascii=False) + "\n")
    n1 = sum(1 for _, n in cnt.items() if n >= 1)
    n2 = sum(1 for _, n in cnt.items() if n >= 2)
    n5 = sum(1 for _, n in cnt.items() if n >= 5)
    print("完成：mapped %d 行 · 排除 test %d · 抽出 %d（失败 %d）· 唯一模板 %d"
          "（support>=2: %d · >=5: %d）· %.1fs"
          % (n_rows, n_test, n_ok, n_fail, n1, n2, n5, time.time() - t0))
    print("输出 -> %s" % OUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
