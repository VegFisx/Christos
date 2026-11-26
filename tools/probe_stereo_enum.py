# -*- coding: utf-8 -*-
"""量化：对 flat-only 案例的 coverage 产物做有界立体枚举，能救回多少。

口径：
  · got 先 RemoveStereochemistry，再用 RDKit EnumerateStereoisomers 枚举；
  · 上限 N（默认 16）个立体异构体；want 在枚举集里 = 可救回；
  · want 本身没立体标记 -> 加一个「平面版」即可救回（单独计数）。
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

ROOT = Path(__file__).resolve().parents[1]
for _p in (ROOT / "libs",):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from rdkit import Chem, RDLogger  # noqa: E402
from rdkit.Chem.EnumerateStereoisomers import (  # noqa: E402
    EnumerateStereoisomers, StereoEnumerationOptions)

RDLogger.DisableLog("rdApp.*")


def canon(s):
    m = Chem.MolFromSmiles(s) if s else None
    return Chem.MolToSmiles(m) if m is not None else ""


def has_stereo(s):
    return ("@" in s) or ("/" in s) or ("\\" in s)


def enum_up_to(smi, cap):
    m = Chem.MolFromSmiles(smi)
    if m is None:
        return []
    Chem.RemoveStereochemistry(m)
    opts = StereoEnumerationOptions(maxIsomers=cap, onlyUnassigned=False,
                                    unique=True, tryEmbedding=False)
    out = []
    try:
        for x in EnumerateStereoisomers(m, options=opts):
            out.append(Chem.MolToSmiles(x))
            if len(out) >= cap:
                break
    except Exception:
        return []
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cases", nargs="?",
                    default=str(ROOT / "reports" / "flat_only_cases.json"))
    ap.add_argument("--cap", type=int, default=16)
    a = ap.parse_args()
    cases = json.loads(Path(a.cases).read_text(encoding="utf-8"))
    print("flat-only %d 条；枚举上限 %d" % (len(cases), a.cap))

    n_flat_want = n_rec = 0
    need = Counter()
    n_centers = Counter()
    fail_centers = Counter()
    for c in cases:
        want, got = c["want"], c["got"]
        if not has_stereo(want):
            n_flat_want += 1
            need[0] += 1
            continue
        mw = Chem.MolFromSmiles(want)
        n_centers[len(Chem.FindMolChiralCenters(mw, includeUnassigned=True,
                                                useLegacyImplementation=False))] += 1
        en = enum_up_to(got, a.cap)
        if want in en:
            n_rec += 1
            need[len(en)] += 1
        else:
            # 记录失败案例的中心数，判断是不是被上限截断
            mg = Chem.MolFromSmiles(got)
            fail_centers[len(Chem.FindMolChiralCenters(mg, includeUnassigned=True,
                                                       useLegacyImplementation=False))] += 1
    m = len(cases)
    print("文献产物本身无立体标记：%d（加平面版即可）" % n_flat_want)
    print("立体枚举可救回：%d/%d = %.1f%%（不含平面版）"
          % (n_rec, m, 100.0 * n_rec / max(1, m)))
    print("合计可救回：%d/%d = %.1f%%"
          % (n_rec + n_flat_want, m, 100.0 * (n_rec + n_flat_want) / max(1, m)))
    print("救回所需枚举数分布：", dict(sorted(need.items())))
    print("失败案例的 got 中心数分布：", dict(sorted(fail_centers.items())))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
