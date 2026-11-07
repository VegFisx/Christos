# -*- coding: utf-8 -*-
"""一次性探针：炮制规则的「路径层」验证（多轮枚举 + 文献中间体追踪）。

口径（用户 2026-10-31 定）：文献中间体能在多轮枚举中出现，即算路径相近。
结构一律取自 tcm.db（只读 URI），不手写 SMILES。

输出：reports/_paozhi_smoke/paths2/<case>/ 下的 csv/tsv/meta。
"""
import csv
import glob
import json
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
OUT = os.path.join(STAGE, "reports", "_paozhi_smoke", "paths2")
PY = r"D:\TCMAI\venv\Scripts\python.exe"
DB = "file:D:/TCMAI/tcm.db?mode=ro"


def db_row(iid):
    con = sqlite3.connect(DB, uri=True)
    try:
        cur = con.cursor()
        cur.execute("SELECT ingredient_id, name_en, formula, smiles, inchi_key "
                    "FROM compounds WHERE ingredient_id=?", (iid,))
        return cur.fetchone()
    finally:
        con.close()


# case: (标签, 种子 ingredient_id, 条件, 轮数, [(目标标签, 匹配方式, 值)])
CASES = [
    ("ginsenoside_Rb1", "HBIN027729", "炮制·蒸制", 3, [
        ("Rg3", "key", "HBIN003457"),
        ("Rg3(20S)", "key", "HBIN003500"),
        ("Rg5", "key", "HBIN027756"),
        ("Rk1", "key", "HBIN027782"),
    ]),
    ("arecoline", "HBIN016699", "炮制·炒焦", 3, [
        ("norarecoline", "formula", "C7H11NO2"),
    ]),
    ("CATR", "HBIN019719", "炮制·炒黄", 3, [
        ("ATR骨架", "formula", "C30H46O16S2"),
    ]),
    ("JNB", "HBIN031562", "炮制·醋炙", 3, [
        ("JNB开环酸", "formula", "C20H28O5"),
    ]),
]


def targets_resolved(specs):
    out = []
    for label, kind, val in specs:
        if kind == "key":
            row = db_row(val)
            if not row or not row[4]:
                print("  [WARN] 目标 %s (%s) 在 tcm.db 取不到 inchi_key" % (label, val))
                continue
            out.append((label, "key", row[4][:14].upper()))
        else:
            out.append((label, "formula", val))
    return out


def run_case(tag, seed_smi, cond, rounds):
    d = os.path.join(OUT, tag)
    os.makedirs(d, exist_ok=True)
    before = set(glob.glob(os.path.join(d, "*.csv")))
    cmd = [PY, "-I", CLI, "predict", "--smiles", seed_smi, "--cond", cond,
           "--rounds", str(rounds), "--limit", "1", "--max-pairs", "400",
           "--out", d, "--no-report"]
    p = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                       errors="replace", timeout=1800)
    if p.returncode != 0:
        print("  [FAIL] " + (p.stdout or "")[-500:] + (p.stderr or "")[-500:])
        return None
    new = [f for f in glob.glob(os.path.join(d, "*.csv")) if f not in before]
    if not new:
        return []
    with open(max(new, key=os.path.getmtime), encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def main():
    summary = []
    for tag, iid, cond, rounds, specs in CASES:
        row = db_row(iid)
        if not row or not row[3]:
            print("== %s：tcm.db 取不到结构" % tag)
            continue
        _iid, name, formula, smi, ikey = row
        print("=" * 78)
        print("== %s | %s | %s | %s | %s" % (tag, name, formula, cond, (smi or "")[:60]))
        rows = run_case(tag, smi, cond, rounds)
        if rows is None:
            continue
        by_round = {}
        for r in rows:
            try:
                rd = int(r.get("round") or 0)
            except Exception:
                rd = 0
            by_round.setdefault(rd, []).append(r)
        print("   各轮产物数：" + "  ".join("r%d=%d" % (k, len(v)) for k, v in sorted(by_round.items())))
        tgt = targets_resolved(specs)
        for label, kind, val in tgt:
            hits = []
            for r in rows:
                if kind == "key":
                    ok = (r.get("product_inchikey") or "")[:14].upper() == val
                else:
                    ok = (r.get("formula") or "") == val
                if ok:
                    hits.append(r)
            rounds_seen = sorted({int(h.get("round") or 0) for h in hits})
            if hits:
                print("   [命中] %-12s 轮次 %s  产物 %d 条" % (label, rounds_seen, len(hits)))
                for h in hits[:3]:
                    print("        r%s %-26s <- %s" % (h.get("round"),
                                                       (h.get("product_smiles") or "")[:46],
                                                       (h.get("rule_name") or "")))
            else:
                print("   [未命中] %-12s (max round %d)" % (label, max(by_round) if by_round else 0))
            summary.append((tag, label, bool(hits), rounds_seen))
    print("=" * 78)
    print("汇总：命中 %d / 共 %d" % (sum(1 for x in summary if x[2]), len(summary)))
    json.dump([{"case": a, "target": b, "hit": c, "rounds": d} for a, b, c, d in summary],
              open(os.path.join(OUT, "summary.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
