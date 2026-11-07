# -*- coding: utf-8 -*-
# 第四十三轮探针①：黑名单泛化聚焦复测
#   用 COCONUT 留出目标（64 个，非原 56）重跑黑名单里的 54 条 never-usable + 3 条 no-op，
#   看是否仍"基本 0 可用"。判据/应用逻辑与 tools/audit_retro_templates.py 完全一致。
# 输出：reports/_holdout_blacklist_check.json + 屏幕表格。
import json
import sys
import time
from collections import Counter
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

STAGE = Path(r"D:\ProgramData\DSHNS\chemreact-staging")
for _p in (STAGE / "libs", STAGE / "tools", STAGE / "core"):
    if _p.is_dir() and str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from rdkit import Chem, RDLogger                        # noqa: E402
from rdkit.Chem import rdChemReactions                  # noqa: E402
import retro_search as rs                               # noqa: E402

RDLogger.DisableLog("rdApp.*")

HOLDOUT = STAGE / "reports" / "_holdout_targets_coconut.txt"
BLACKLIST = STAGE / "reports" / "retro_template_blacklist.json"
OLD_AUDIT = STAGE / "reports" / "retro_template_audit.jsonl"
OUT = STAGE / "reports" / "_holdout_blacklist_check.json"


def main() -> int:
    t0 = time.time()
    bl = json.loads(BLACKLIST.read_text(encoding="utf-8"))
    kinds = {}
    for e in bl.get("entries", []):
        kinds[str(e.get("smarts"))] = "never_usable"
    for e in bl.get("noop_entries", []):
        kinds[str(e.get("smarts"))] = "noop"

    targets = []
    seen = set()
    for line in open(HOLDOUT, encoding="utf-8"):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        smi = line.split("\t")[0].strip()
        m = Chem.MolFromSmiles(smi)
        if m is None or smi in seen:
            continue
        seen.add(smi)
        targets.append(Chem.MolToSmiles(m))
    print("留出目标 %d 个（来自 %s）" % (len(targets), HOLDOUT.name), flush=True)

    old = {}
    if OLD_AUDIT.exists():
        for line in open(OLD_AUDIT, encoding="utf-8"):
            line = line.strip()
            if line:
                r = json.loads(line)
                old[str(r.get("smarts"))] = r

    sel = []
    n_compile_fail = 0
    for sm in kinds:
        try:
            rx = rdChemReactions.ReactionFromSmarts(sm)
        except Exception:
            rx = None
        if rx is None or rx.GetNumReactantTemplates() != 1:
            n_compile_fail += 1
            continue
        sel.append((sm, rx))
    print("黑名单模板 %d 条（可编译 %d，失败 %d）"
          % (len(kinds), len(sel), n_compile_fail), flush=True)

    rows = []
    for k, (sm, rx) in enumerate(sel, 1):
        c = Counter()
        for tgt in targets:
            m = Chem.MolFromSmiles(tgt)
            if m is None:
                continue
            try:
                outs = rx.RunReactants((m,))
            except Exception:
                c["run_fail"] += 1
                continue
            for tup in outs:
                prec = tuple(rs.canon(Chem.MolToSmiles(p)) for p in tup if p is not None)
                prec = tuple(p for p in prec if p)
                if not prec:
                    continue
                ok, why = rs.step_usability(tgt, prec)
                c["n_try"] += 1
                if ok:
                    c["n_usable"] += 1
                else:
                    c[why] += 1
        o = old.get(sm, {})
        rows.append({"smarts": sm, "kind": kinds[sm],
                     "old_n_try": int(o.get("n_try", -1)), "old_n_usable": int(o.get("n_usable", -1)),
                     "new_n_try": int(c.get("n_try", 0)), "new_n_usable": int(c.get("n_usable", 0)),
                     "new_reasons": {k2: int(v) for k2, v in c.items()
                                     if k2.startswith("R") or k2.startswith("run_")}})
        if k % 10 == 0:
            print("   ... %d/%d（%.0fs）" % (k, len(sel), time.time() - t0), flush=True)

    tot_try = sum(r["new_n_try"] for r in rows)
    tot_us = sum(r["new_n_usable"] for r in rows)
    n_zero = sum(1 for r in rows if r["new_n_usable"] == 0 and r["new_n_try"] > 0)
    n_hit = sum(1 for r in rows if r["new_n_try"] > 0)
    usable_rows = sorted([r for r in rows if r["new_n_usable"] > 0],
                         key=lambda r: -r["new_n_usable"])
    out = {"targets": len(targets), "holdout_file": HOLDOUT.name,
           "n_templates": len(rows), "totals": {"n_try": tot_try, "n_usable": tot_us,
                                                "usable_rate": round(tot_us / max(1, tot_try), 4)},
           "n_with_hits": n_hit, "n_zero_usable_with_hits": n_zero,
           "rows": rows, "seconds": round(time.time() - t0, 1)}
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")

    print("=" * 74)
    print("留出复测：黑名单 %d 条 · 有命中 %d 条 · 其中仍 0 可用 %d 条" % (len(rows), n_hit, n_zero))
    print("合计：try %d · 可用 %d（%.2f%%）" % (tot_try, tot_us, 100 * tot_us / max(1, tot_try)))
    for r in usable_rows[:8]:
        print("  ★ 产出可用的：%s… old %d/%d -> new %d/%d"
              % (r["smarts"][:56], r["old_n_try"], r["old_n_usable"],
                 r["new_n_try"], r["new_n_usable"]))
    print("写出：%s（%.1fs）" % (OUT.name, time.time() - t0))
    return 0


if __name__ == "__main__":
    sys.exit(main())
