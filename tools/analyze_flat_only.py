# -*- coding: utf-8 -*-
"""分析「骨架对、精确立体不对」的案例：立体是怎么丢的。

输入：tools/probe_uspto_train_coverage.py --dump-flat 写出的 JSON。
输出：按类别计数 + 每条案例的立体中心摘要。
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

RDLogger.DisableLog("rdApp.*")


def stereo_marks(s: str) -> bool:
    return ("@" in s) or ("/" in s) or ("\\" in s)


def centers(s: str):
    m = Chem.MolFromSmiles(s)
    if m is None:
        return []
    return Chem.FindMolChiralCenters(m, includeUnassigned=True,
                                     useLegacyImplementation=False)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("cases", nargs="?",
                    default=str(ROOT / "reports" / "flat_only_cases.json"))
    a = ap.parse_args()
    cases = json.loads(Path(a.cases).read_text(encoding="utf-8"))
    print("flat-only 案例 %d 条" % len(cases))

    cnt = Counter()
    n_centers = Counter()
    tpl_at = 0
    unassigned_got = 0
    for c in cases:
        want, got, tpl = c["want"], c["got"], c.get("template") or ""
        if "@" in tpl:
            tpl_at += 1
        want_st = stereo_marks(want)
        got_st = stereo_marks(got)
        if want_st and not got_st:
            kind = "got_flat"
        elif want_st and got_st and want != got:
            kind = "wrong_stereo"
        else:
            kind = "other"
        cnt[kind] += 1
        cw = centers(want)
        cg = centers(got)
        n_centers[len(cw)] += 1
        if any(lbl == "?" for _i, lbl in cg):
            unassigned_got += 1
        if kind == "other":
            print("  [other] i=%s want=%s got=%s" % (c["i"], want, got))
    print("类别：", dict(cnt))
    print("want 的立体中心数分布：", dict(sorted(n_centers.items())))
    print("模板 SMARTS 含 '@'：%d/%d" % (tpl_at, len(cases)))
    print("got 里仍有未指定中心：%d/%d" % (unassigned_got, len(cases)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
