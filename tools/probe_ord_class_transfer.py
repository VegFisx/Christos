# -*- coding: utf-8 -*-
r"""C2 探针（2026-11-10）第二半：同类里还有一条记录时，能不能救回来？

第 136 轮证明「放宽模板环境」不涨召回；第 135 轮证明「放宽阈值」只在中等频次有效。
两者都没回答一个问题：

    如果语料里同一个反应类还有**第二条**记录，用它挖出来的模板能不能重现第一条的产物？

若能，缺的就是语料规模（同一类多几条记录 → 多几个模板 → 覆盖更多底物）；
若不能，说明模板式管线连「同类样例迁移」都做不到，问题在架构。

做法：
1. 复用 `bench_class_strata.build_sample()`，按 `class_sig()` 分组；
2. 取稀有组（样本内 ≤3 条），对组内每条记录 A，用**另一条**记录 B 的映射反应挖 rdchiral 模板；
3. 用该模板对 A 的底物跑 `RunReactants`，按去映射规范化 SMILES 比对 A 的记录产物；
4. 同时记录「组内条数」与「模板是否命中」。

判读：命中率高 → 覆盖问题；接近 0 → 架构问题。
"""
from __future__ import annotations

import json
import random
import sys
from collections import Counter, defaultdict
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

STAGE = Path(r"D:\ProgramData\DSHNS\chemreact-staging")
for _p in (STAGE / "libs", STAGE / "tools"):
    sys.path.insert(0, str(_p))

import bench_class_strata as B  # noqa: E402

from rdkit import Chem, RDLogger  # noqa: E402
from rdkit.Chem import AllChem  # noqa: E402

import rdchiral.template_extractor as te  # noqa: E402
from rdchiral.template_extractor import extract_from_reaction  # noqa: E402

RDLogger.DisableLog("rdApp.*")
te.VERBOSE = False

OUT = STAGE / "reports" / "ord_class_transfer_20261110.json"
N_SAMPLE = 120

import re  # noqa: E402

ATOM_Q = re.compile(r"\[([A-Za-z][a-z]?|\*|c|n|o|s|p)([^\]]*):(\d+)\]")


def relax(smarts):
    """Strip atom environments down to element plus map number."""
    if not smarts:
        return smarts
    return ATOM_Q.sub(lambda m: "[%s:%s]" % (m.group(1), m.group(3)), smarts)


def flat(smi):
    m = Chem.MolFromSmiles(smi) if smi else None
    if m is None:
        return ""
    for a in m.GetAtoms():
        a.SetAtomMapNum(0)
    return Chem.MolToSmiles(m)


def apply_template(tpl, reactants):
    """Apply one template SMARTS to the mapped reactants; return product SMILES list."""
    rxn = AllChem.ReactionFromSmarts(tpl, useSmiles=False)
    rmol = Chem.MolFromSmiles(reactants)
    if rxn is None or rmol is None:
        return []
    comps = [c for c in reactants.split(".") if ":" in c]
    mols = [Chem.MolFromSmiles(c) for c in comps]
    mols = [m for m in mols if m is not None]
    out = []
    n = rxn.GetNumReactantTemplates()
    import itertools
    combos = [mols] if n == 1 else (list(itertools.permutations(mols, n)) if len(mols) >= n else [])
    for combo in combos:
        try:
            prods = rxn.RunReactants(tuple(combo))
        except Exception:
            continue
        for pset in prods:
            parts = []
            ok = True
            for p in pset:
                try:
                    Chem.SanitizeMol(p)
                except Exception:
                    ok = False
                    break
                parts.append(flat(Chem.MolToSmiles(p)))
            if ok and parts:
                out.append(".".join(sorted(parts)))
    return out


def main() -> int:
    recs = B.build_sample()
    groups = defaultdict(list)
    for r in recs:
        s = B.class_sig(r["reactants"] + ">>" + r["product"])
        if s:
            groups[s].append(r)
    rare = {s: v for s, v in groups.items() if 2 <= len(v) <= 3}
    print("groups %d, rare groups with >=2 members %d" % (len(groups), len(rare)), flush=True)

    rng = random.Random(B.SEED)
    keys = rng.sample(sorted(rare, key=str), min(N_SAMPLE, len(rare)))

    rows = []
    for s in keys:
        members = rare[s]
        for i, a in enumerate(members):
            donours = [b for j, b in enumerate(members) if j != i]
            target = flat(a["product"])
            hit = False
            hit_relaxed = False
            tried = 0
            for b in donours:
                try:
                    t = extract_from_reaction({"reactants": b["reactants"],
                                               "products": b["product"], "_id": "x"})
                except Exception:
                    t = None
                tpl = (t or {}).get("reaction_smarts")
                if not tpl:
                    continue
                tried += 1
                prods = apply_template(tpl, a["reactants"])
                if target and target in prods:
                    hit = True
                if not hit_relaxed:
                    rprods = apply_template(relax(tpl), a["reactants"])
                    if target and target in rprods:
                        hit_relaxed = True
                if hit and hit_relaxed:
                    break
            rows.append({"reaction_id": a.get("reaction_id"), "group_size": len(members),
                         "donours": len(donours), "templates_tried": tried, "hit": hit,
                         "hit_relaxed": hit_relaxed})

    n = len(rows)
    hits = sum(1 for r in rows if r["hit"])
    hits_r = sum(1 for r in rows if r["hit_relaxed"])
    by_size = Counter(r["group_size"] for r in rows)
    hit_by_size = Counter(r["group_size"] for r in rows if r["hit"])
    payload = {
        "generated_at": __import__("datetime").datetime.now().isoformat(timespec="seconds"),
        "n_records": len(recs),
        "n_rare_groups": len(rare),
        "n_tested": n,
        "hits": hits,
        "recall": round(hits / n, 4) if n else None,
        "hits_relaxed": hits_r,
        "recall_relaxed": round(hits_r / n, 4) if n else None,
        "group_sizes": dict(by_size),
        "hits_by_size": dict(hit_by_size),
        "rows": rows,
    }
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({k: payload[k] for k in ("n_rare_groups", "n_tested", "hits",
                                              "recall", "hits_relaxed",
                                              "recall_relaxed", "group_sizes",
                                              "hits_by_size")}, ensure_ascii=False))
    print("wrote", OUT)
    return 0


if __name__ == "__main__":
    sys.exit(main())
