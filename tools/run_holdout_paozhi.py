"""炮制留出集（预注册）：跑 data/holdout_paozhi.json，与冻结的预期逐条对照。

规则（写死的，不许绕）：

1. 预期字段 ``expected`` 在第一次运行**之前**就提交进库里（commit 97b6f78）；
   本脚本只读它，**不写**它。
2. 只允许用现有规则与条件档跑；失败了就记失败，不许为留出案例补规则。
3. 输出 ``reports/holdout_paozhi_<日期>.json``，每次都覆盖同名日期文件，
   历史版本靠 git 保留。

用法：

    python tools\\run_holdout_paozhi.py
"""

import argparse
import json
import os
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
for _p in (ROOT / "core", ROOT / "tools"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

import validate_paozhi_paths as V          # noqa: E402

HOLDOUT = ROOT / "data" / "holdout_paozhi.json"
_DB_PATH = os.environ.get("CHEMCREACT_TCM_DB") or "D:/TCMAI/tcm.db"
DB = "file:%s?mode=ro" % _DB_PATH.replace("\\", "/")


def run_one(cur, case, mode="evidence", rounds=1):
    """把 JSON 里的一条案例交给第 88 轮的同一套协议跑。"""
    targets = [
        (t["label"], t["kind"], t["value"], tuple(t.get("family") or ()))
        for t in case["targets"]
    ]
    row = V.run_case(cur, case["id"], case["seed"]["iid"], case["condition"],
                     targets, case.get("bridge") or "",
                     mode=mode, rounds=rounds)
    row["herb_cn"] = case["herb_cn"]
    row["process_cn"] = case["process_cn"]
    row["holdout_strength"] = case["holdout_strength"]
    row["expected"] = case["expected"]
    got = [t.get("status") for t in row.get("targets", [])]
    actual = got[0] if len(got) == 1 else ("consistent" if got and all(g == "consistent" for g in got) else got)
    row["actual_status"] = actual
    row["prediction_hit"] = (str(actual) == case["expected"]["status"])
    return row


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=("evidence", "production"), default="evidence",
                    help="evidence=11条证据规则；production=11条+coverage+立体")
    ap.add_argument("--rounds", type=int, default=1, help="枚举轮数（默认1）")
    ap.add_argument("--holdout", default=str(HOLDOUT),
                    help="留出集 JSON（默认 data/holdout_paozhi.json）")
    a = ap.parse_args()
    mode, rounds = a.mode, max(1, int(a.rounds))
    hold_path = Path(a.holdout).resolve()

    hold = json.loads(hold_path.read_text(encoding="utf-8"))
    con = sqlite3.connect(DB, uri=True)
    cur = con.cursor()

    rows = []
    for case in hold["cases"]:
        r = run_one(cur, case, mode=mode, rounds=rounds)
        rows.append(r)
        exp = case["expected"]["status"]
        act = r["actual_status"]
        mark = "OK " if r["prediction_hit"] else "MISS"
        rule = (r.get("targets") or [{}])[0].get("rule") or "-"
        print("%-4s %-24s expect %-14s got %-14s rule %s"
              % (mark, case["id"], exp, act, rule), flush=True)

    n = len(rows)
    hits = sum(1 for r in rows if r["prediction_hit"])
    statuses = {}
    for r in rows:
        statuses[str(r["actual_status"])] = statuses.get(str(r["actual_status"]), 0) + 1

    try:
        hold_rel = str(hold_path.relative_to(ROOT)).replace("\\", "/")
    except ValueError:
        hold_rel = str(hold_path)
    out = {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "holdout_file": hold_rel,
        "frozen_git_rev": hold.get("frozen_git_rev"),
        "mode": mode,
        "rounds": rounds,
        "n_cases": n,
        "n_prediction_hits": hits,
        "actual_status_counts": statuses,
        "cases": rows,
    }
    _stem = hold_path.stem
    _extra = "" if _stem == "holdout_paozhi" else "_" + _stem.replace("holdout_paozhi_", "")
    suffix = "" if (mode == "evidence" and rounds == 1) else "_%s_r%d" % (mode, rounds)
    dst = ROOT / "reports" / ("holdout_paozhi_%s%s%s.json"
                              % (datetime.now().strftime("%Y%m%d"), _extra, suffix))
    dst.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")

    print()
    print("mode %s | rounds %d | cases %d | prediction hits %d/%d | status counts %s"
          % (mode, rounds, n, hits, n, statuses))
    print("written", dst)
    con.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
