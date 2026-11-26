# -*- coding: utf-8 -*-
"""One-command status report for the remaining chemical-AI backlog.

It does not edit rules or run the expensive release gate.  It checks the
current ledgers, blind/dev artifacts, newest gate record, co-substrate pools and
the family-sweep output.
"""
from __future__ import annotations

import argparse
import glob
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

ROOT = Path(__file__).resolve().parent.parent
RULES = ROOT / "rules" / "rules.json"
BLIND = [
    "holdout_general_organic_blind_20261124.json",
    "holdout_general_organic_blind2_20261124.json",
    "holdout_general_organic_blind3_20261124.json",
    "holdout_general_organic_blind4_20261124.json",
    "holdout_general_organic_blind5_20261124.json",
    "holdout_general_organic_blind6_20261124.json",
]
DEV = "dev_general_organic_20261124.json"
OUT_JSON = ROOT / "reports" / "backlog_status_20261124.json"
OUT_MD = ROOT / "reports" / "backlog_status_20261124.md"

def sha(path):
    h = hashlib.sha256()
    h.update(Path(path).read_bytes())
    return h.hexdigest()

def latest(pattern):
    fs = glob.glob(str(ROOT / pattern))
    return max(fs, key=lambda p: Path(p).stat().st_mtime) if fs else None

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", default=str(OUT_JSON))
    ap.add_argument("--md", default=str(OUT_MD))
    args = ap.parse_args()

    d = json.loads(RULES.read_text(encoding="utf-8"))
    rules = d["rules"]
    active = [r for r in rules if str(r.get("status") or "active") == "active"]
    prov = Counter(str(r.get("provenance") or "unvalidated") for r in rules)
    active_prov = Counter(str(r.get("provenance") or "unvalidated") for r in active)
    pools = []
    validation_pools = 0
    for r in rules:
        for p in r.get("co_substrate_pool") or []:
            # 2026-11-24：标准例验收池带 validation_only，生产枚举已跳过，
            # 不再算作「无门控池」的待办。
            if p.get("validation_only"):
                validation_pools += 1
                continue
            if not p.get("when_solvent") and not p.get("when_template"):
                pools.append({"rule": r["id"], "smiles": p.get("smiles"),
                              "name": p.get("name")})
    gate_file = latest("reports/benchmarks/release-*.json")
    gate = {}
    if gate_file:
        g = json.loads(Path(gate_file).read_text(encoding="utf-8"))
        gate = {"file": Path(gate_file).name, "rev": g.get("git_rev"),
                "verdict": g.get("verdict"),
                "smoke": (g.get("results", {}).get("smoke", {}) or {}).get("counts"),
                "forward": (g.get("results", {}).get("forward", {}) or {}).get("recall")}
    blinds = []
    for name in BLIND + [DEV]:
        p = ROOT / "data" / name
        blinds.append({"file": name, "exists": p.exists(),
                       "sha256": sha(p) if p.exists() else None})
    # latest dev full_lf
    dev_files = glob.glob(str(ROOT / "reports" / "general_organic_full_lf_dev*.json"))
    dev = None
    if dev_files:
        p = max(dev_files, key=lambda x: Path(x).stat().st_mtime)
        x = json.loads(Path(p).read_text(encoding="utf-8"))
        dev = {"file": Path(p).name, "n": x.get("n"), "hits": x.get("hits"),
               "exact": x.get("exact")}
    sweep = ROOT / "reports" / "family_template_sweep_20261124.json"
    sweep_info = {}
    if sweep.exists():
        s = json.loads(sweep.read_text(encoding="utf-8"))
        sweep_info = {f["family"]: len(f.get("candidates") or [])
                      for f in s.get("families") or []}
    out = {
        "rules": {"total": len(rules), "active": len(active),
                  "disabled": len(rules) - len(active),
                  "provenance_total": dict(prov),
                  "provenance_active": dict(active_prov)},
        "default_vs_explore": {
            "default_validated": sum(
                1 for r in active
                if str(r.get("provenance") or "").lower() in ("cited", "secondary")
                and not r.get("paozhi_only")),
            "active_unvalidated": sum(
                1 for r in active
                if str(r.get("provenance") or "unvalidated").lower()
                not in ("cited", "secondary")
                and not r.get("paozhi_only"))},
        "latest_gate": gate,
        "blind_artifacts": blinds,
        "latest_dev_full_lf": dev,
        "family_sweep_candidates": sweep_info,
        "validation_only_pool_items": validation_pools,
        "co_substrate_pools_without_condition_gate": pools,
    }
    Path(args.json).write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")

    lines = ["# Backlog status", ""]
    lines.append("- rules: %d total / %d active / %d disabled" %
                 (len(rules), len(active), len(rules) - len(active)))
    lines.append("- provenance: %s" % dict(prov))
    lines.append("- active unvalidated: %d" % active_prov.get("unvalidated", 0))
    lines.append("- latest gate: %s" % (gate.get("file") if gate else "missing"))
    lines.append("- latest dev full_lf: %s" % (dev if dev else "missing"))
    lines.append("- family sweep: %s" % sweep_info)
    lines.append("- validation-only pool items (not counted): %d" % validation_pools)
    lines.append("- unconstrained co-substrate pools: %d" % len(pools))
    Path(args.md).write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))
    print("written", args.json, args.md)
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
