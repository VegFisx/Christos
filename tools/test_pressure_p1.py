# -*- coding: utf-8 -*-
"""第 142 轮（压力 P1：表示层）的回归测试。

跑法：
    python tools\\test_pressure_p1.py

只读。P1 的契约只有一句：**压力必须能从命令行走到条件、台账与运行记录，
且产物集合一个字都不许变**。这条测试就是守它的。

    PASSED 说明「压力被记录了」；
    如果哪天有人拿压力去判活/调速率，第 5 组会失败（产物数变了）。
"""
from __future__ import annotations

import csv
import json
import subprocess
import sys
import tempfile
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:                                     # noqa: BLE001
        pass

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
BRIDGE = ROOT / "integration" / "tcmai_bridge" / "chemreact.py"
PY = sys.executable
sys.path.insert(0, str(ROOT / "core"))
sys.path.insert(0, str(ROOT / "conditions"))

_fail = 0


def check(name: str, ok: bool, detail: str = "") -> None:
    global _fail
    print(("  [ok]   " if ok else "  [FAIL] ") + name + (("  " + detail) if detail else ""))
    if not ok:
        _fail += 1


def run_predict(outdir: Path, *extra: str) -> tuple[list[dict], dict]:
    cmd = [PY, "-u", str(BRIDGE), "predict", "--herb", "甘草", "--limit", "2",
           "--rounds", "1", "--cond", "煎煮", "--out", str(outdir), "--no-report",
           *extra]
    p = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                       errors="replace", timeout=1800)
    if p.returncode != 0:
        raise RuntimeError("predict 失败：\n" + (p.stdout or "")[-1500:] + (p.stderr or "")[-1500:])
    csvs = sorted(outdir.glob("*.csv"))
    metas = sorted(outdir.glob("*.meta.json"))
    rows = list(csv.DictReader(csvs[0].open(encoding="utf-8-sig")))
    meta = json.loads(metas[0].read_text(encoding="utf-8"))
    return rows, meta


def main() -> int:
    import model as M
    import query_base as QB

    print("1）条件模型")
    c = M.Conditions()
    check("默认压力 1.0 atm", c.pressure_atm == 1.0, str(c.pressure_atm))
    check("1.0 atm 通过校验", c.validate() == [], str(c.validate()))
    check("2.5 atm 合法", M.Conditions(pressure_atm=2.5).validate() == [])
    check("0 atm 被拒", any("压力" in x for x in M.Conditions(pressure_atm=0).validate()))
    check("400 atm 被拒", any("压力" in x for x in M.Conditions(pressure_atm=400).validate()))
    check("0.05 atm 合法（真空）", M.Conditions(pressure_atm=0.05).validate() == [])

    print("2）RunSpec → Conditions")
    spec = QB.RunSpec(seeds=[], cond_name="煎煮")
    check("默认不覆盖（预设仍是 1.0）", spec.cond().pressure_atm == 1.0)
    spec2 = QB.RunSpec(seeds=[], cond_name="煎煮", pressure_atm=2.5)
    check("显式压力写进条件", spec2.cond().pressure_atm == 2.5, str(spec2.cond().pressure_atm))
    check("其它条件不受影响", spec2.cond().temperature == 100.0)

    print("3）台账字段")
    check("PATH_FIELDS 含 pressure_atm", "pressure_atm" in QB.PATH_FIELDS)

    print("4）端到端：命令行 → 台账 / 运行记录")
    with tempfile.TemporaryDirectory() as td:
        rows, meta = run_predict(Path(td) / "atm25", "--pressure-atm", "2.5")
        vals = {r.get("pressure_atm", "") for r in rows}
        check("台账每行都是 2.5", vals == {"2.5"}, str(sorted(vals)))
        cd = (meta.get("condition_details") or {}).get("pressure_atm") or {}
        check("运行记录里有压力", float(cd.get("value", 0) or 0) == 2.5, str(cd.get("value")))
        check("运行记录写明压力的作用边界",
          ("沸点" in str(cd.get("note", ""))) or ("不参与" in str(cd.get("note", ""))),
          str(cd.get("note")))
        sw = (meta.get("switches") or {})
        check("switches 记录压力", float(sw.get("pressure_atm", 0) or 0) == 2.5)
        n_atm = len(rows)

    print("5）P1 契约：压力不改变产物")
    with tempfile.TemporaryDirectory() as td:
        rows2, _meta2 = run_predict(Path(td) / "base")
        n_base = len(rows2)
        check("默认压力下的产物数", n_base > 0, str(n_base))
        check("2.5 atm 与默认产物数相同", n_atm == n_base, "%d vs %d" % (n_atm, n_base))
        base_p = {r["pressure_atm"] for r in rows2}
        check("默认台账压力是 1.0", base_p == {"1.0"}, str(sorted(base_p)))

    print()
    print("失败 %d 项" % _fail)
    return 0 if _fail == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
