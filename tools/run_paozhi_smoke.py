# -*- coding: utf-8 -*-
"""Run the paozhi smoke tests (limit 6, 1 round) and print one compact row per run.

Usage:
  python -I tools/run_paozhi_smoke.py            # 环境变量 CHEMREACT_PY 可覆盖解释器

Runs:
  A: 甘草 盐炙 / 姜炙
  C: 甘草 蜜炙 / 醋炙 (adjuvant on), 醋炙 --no-paozhi-adjuvant (control)
  guard: 甘草 煎煮 (no adjuvant outside paozhi)
"""
import json
import os
import subprocess
import sys
import time
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# 2026-11-04: venv 已修好（pyvenv.cfg 曾被写坏成一段终端输出 + 旧 home 路径，
# 报 "No Python at 'C:\Users\Vegfish\...'"）。回到 venv 解释器；CHEMREACT_PY 仍可覆盖。
PY = os.environ.get("CHEMREACT_PY") or r"D:/TCMAI/venv/Scripts/python.exe"
CLI = Path("D:/ProgramData/DSHNS/chemreact-staging/integration/tcmai_bridge/chemreact.py")
OUT = Path("D:/ProgramData/DSHNS/chemreact-staging/reports/_paozhi_smoke")

RUNS = [
    ("A_yanyan", ["--cond", "炮制·盐炙"]),
    ("A_jiangyan", ["--cond", "炮制·姜炙"]),
    ("C_miyan_adj", ["--cond", "炮制·蜜炙"]),
    ("C_miyan_noadj", ["--cond", "炮制·蜜炙", "--no-paozhi-adjuvant"]),
    ("C_cuyan_adj", ["--cond", "炮制·醋炙"]),
    ("C_cuyan_noadj", ["--cond", "炮制·醋炙", "--no-paozhi-adjuvant"]),
    ("C_cuyan_envoff", ["--cond", "炮制·醋炙"], {"CHEMCREACT_PAOZHI_ADJUVANT": "0"}),
    ("guard_jiandao", ["--cond", "煎煮"]),
]


def newest_meta(d: Path):
    metas = sorted(d.glob("*.meta.json"), key=lambda p: p.stat().st_mtime)
    return metas[-1] if metas else None


def main() -> int:
    print("tag, cond, products, new, input, co_substrates, from_adjuvant, seconds")
    wanted = set(sys.argv[1:])
    for tag, extra, *rest in RUNS:
        if wanted and tag not in wanted:
            continue
        out = OUT / ("third_" + tag)
        out.mkdir(parents=True, exist_ok=True)
        before = set(out.glob("*.meta.json"))
        cmd = [PY, str(CLI), "predict", "--herb", "甘草", "--limit", "6", "--rounds", "1",
               "--out", str(out), "--no-report"] + extra
        env = dict(os.environ)
        if rest:
            env.update(rest[0])
        t0 = time.time()
        r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                           errors="replace", env=env)
        wall = time.time() - t0
        if r.returncode != 0:
            print(f"[FAIL] {tag}: rc={r.returncode}")
            print((r.stdout or "")[-800:])
            print((r.stderr or "")[-800:])
            continue
        meta = newest_meta(out)
        if meta is None or meta in before:
            print(f"[FAIL] {tag}: no new meta json")
            continue
        d = json.loads(meta.read_text(encoding="utf-8"))
        pr = d.get("processing") or {}
        st = d.get("stats") or {}
        cond = (d.get("cond_name") or "")
        print("%s, %s, %s, %s, %s, %s, %s, %.2f (engine %.2f)" % (
            tag, cond, st.get("n_products"), pr.get("n_new_products"),
            pr.get("n_input_compounds"), pr.get("n_co_substrates"),
            pr.get("n_products_from_adjuvant"), wall, st.get("seconds") or 0.0))
        if pr.get("co_substrates"):
            print("    co-substrates: " + ", ".join(
                "%s(%s)" % (c.get("name"), c.get("formula") or "?")
                for c in pr["co_substrates"]))
        print("    meta: " + meta.name)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
