# -*- coding: utf-8 -*-
# 一次性：剥后模板在甘草 3 成分上到底哪几条触发、产出什么（复核 2290 这个数）
import csv
import json
import sys
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

STAGE = Path(r"D:\ProgramData\DSHNS\chemreact-staging")
for _p in (STAGE / "libs", STAGE / "tools"):
    if _p.is_dir() and str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from rdkit import Chem, RDLogger                        # noqa: E402
from rdkit.Chem import rdChemReactions                  # noqa: E402

RDLogger.DisableLog("rdApp.*")

mols = []
seen = set()
with open(STAGE / "reports" / "query_inventory_paths.csv", encoding="utf-8-sig", newline="") as f:
    for row in csv.DictReader(f):
        smi = str(row.get("source_smiles") or "").strip()
        m = Chem.MolFromSmiles(smi) if smi else None
        if m is None:
            continue
        c = Chem.MolToSmiles(m)
        if c not in seen:
            seen.add(c)
            mols.append(m)
print("成分 %d 个" % len(mols))

for line in open(STAGE / "reports" / "_strip_spectators_probe.jsonl", encoding="utf-8"):
    r = json.loads(line)
    if not r.get("compiled"):
        continue
    rx = rdChemReactions.ReactionFromSmarts(r["stripped_smarts"])
    fired, sample = 0, []
    for i in range(len(mols)):
        for j in range(len(mols)):
            if i == j:
                continue
            try:
                outs = rx.RunReactants((mols[i], mols[j]))
            except Exception:
                continue
            for tup in outs:
                ps = []
                good = True
                for pm in tup:
                    try:
                        Chem.SanitizeMol(pm)
                        ps.append(Chem.MolToSmiles(pm))
                    except Exception:
                        good = False
                if good:
                    fired += 1
                    if len(sample) < 2:
                        sample.append(ps)
    if fired:
        print("-" * 90)
        print("行 %s 触发 %d · 剥掉 %s" % (r["line"], fired, r["spectators"]))
        print("  模板:", r["stripped_smarts"][:120])
        for ps in sample:
            for p in ps[:3]:
                print("  产物样例:", p[:100])
