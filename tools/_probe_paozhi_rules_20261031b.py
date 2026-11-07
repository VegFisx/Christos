# -*- coding: utf-8 -*-
"""一次性探针：用 tcm.db 里的真实结构跑 5 条炮制文献规则的 CLI 级验证。

只读 tcm.db（mode=ro）；不写库；输出落在 reports/_paozhi_smoke/rule_tests2/。
"""
import csv
import glob
import os
import sqlite3
import subprocess
import sys

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

STAGE = r"D:\ProgramData\DSHNS\chemreact-staging"
CLI = os.path.join(STAGE, "integration", "tcmai_bridge", "chemreact.py")
OUT = os.path.join(STAGE, "reports", "_paozhi_smoke", "rule_tests2")
PY = r"D:\TCMAI\venv\Scripts\python.exe"

IDS = {
    "arecoline": "HBIN016699",
    "CATR": "HBIN019719",
    "JNB": "HBIN031562",
}


def db_smiles():
    con = sqlite3.connect("file:D:/TCMAI/tcm.db?mode=ro", uri=True)
    try:
        cur = con.cursor()
        out = {}
        for name, iid in IDS.items():
            cur.execute("SELECT smiles FROM compounds WHERE ingredient_id=?", (iid,))
            row = cur.fetchone()
            out[name] = row[0] if row else None
        return out
    finally:
        con.close()


CASES = [
    ("arecoline", "炮制·炒焦", "demethylation_n_001"),
    ("CATR", "炮制·炒黄", "decarboxylation_001"),
    ("JNB", "炮制·醋炙", "hydrolysis_epoxide_001"),
    ("JNB", "炮制·醋炙", "hydrolysis_lactone_5ring_001"),
    ("allyl_alcohol", "炮制·醋炙", "oxidation_allylic_alcohol_001"),
    ("diethyl_ether", "炮制·醋炙", "cleavage_ether_acyclic_001"),
]
EXTRA = {"allyl_alcohol": "C=CCO", "diethyl_ether": "CCOCC"}


def run(smiles, cond, tag):
    d = os.path.join(OUT, tag)
    os.makedirs(d, exist_ok=True)
    before = set(glob.glob(os.path.join(d, "*.csv")))
    cmd = [PY, "-I", CLI, "predict", "--smiles", smiles, "--cond", cond,
           "--rounds", "1", "--limit", "1", "--out", d, "--no-report"]
    p = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                       errors="replace")
    if p.returncode != 0:
        return None, (p.stdout or "") + (p.stderr or "")
    new = [f for f in glob.glob(os.path.join(d, "*.csv")) if f not in before]
    if not new:
        return [], ""
    rows = []
    with open(max(new, key=os.path.getmtime), encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    return rows, ""


def main():
    smi = db_smiles()
    failures = 0
    for name, cond, rule in CASES:
        s = smi.get(name) or EXTRA.get(name)
        if not s:
            print("[MISS] %s：tcm.db 里取不到结构" % name)
            failures += 1
            continue
        rows, err = run(s, cond, "%s_%s_%s" % (name, cond.replace("·", "_"), rule))
        if rows is None:
            print("[FAIL] %s %s\n%s" % (name, cond, err[-800:]))
            failures += 1
            continue
        hits = [r for r in rows if (r.get("rule_name") or "") == rule]
        print("== %-14s %-8s 产物 %3d 行；%s 命中 %d" % (name, cond, len(rows), rule, len(hits)))
        for r in hits[:4]:
            print("    ", r.get("product_smiles", "")[:95],
                  "|", r.get("product_formula", ""))
    print("FAILURES=%d" % failures)


if __name__ == "__main__":
    main()
