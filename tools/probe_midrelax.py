# -*- coding: utf-8 -*-
r"""中间档放宽（2026-11-10）：丢掉 H 数 / 度数 / 环大小，**保留**键级、芳香性、电荷。

背景：第 136 轮只试了最松的一档（`[O;H0;D3;+0:1]` → `[O:1]`，元素+映射号），稀有层召回
12.5% 一点没动、候选还涨了 71%。那一档把「双键 vs 单键」「芳香 vs 脂肪」也丢了，等于换了
一类化学；中间档只丢「同一个原子在自己分子里的处境」（有几个氢、连了几根键、在不在环上），
这是化学上真正该等价的部分。

预注册判据（先写在这里，再跑）：
    · 稀有层（≤3 次）120 条，raw 基线 15/120
    · 中间档需要 ≥ 25/120（+10 条）才算有信号，否则杀掉这条路
    · 顺带看中等层（10–99 次）与常见层（≥100 次），常见层不许掉超过 5 条

用法：
    python _diag/probe_midrelax.py
    STRATA_N=120 python _diag/probe_midrelax.py
"""
from __future__ import annotations

import io
import json
import os
import random
import re
import sys
import time
from collections import Counter

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

STAGE = r"D:\ProgramData\DSHNS\chemreact-staging"
for _p in (os.path.join(STAGE, "libs"), os.path.join(STAGE, "core"),
           os.path.join(STAGE, "conditions"), os.path.join(STAGE, "tools")):
    sys.path.insert(0, _p)

from rdkit import Chem, RDLogger  # noqa: E402
from rdkit.Chem import AllChem  # noqa: E402

RDLogger.DisableLog("rdApp.*")

import bench_class_strata as B  # noqa: E402

POOL = os.path.join(STAGE, "reports", "mined_forward_templates_full_s5.jsonl")
OUT = os.path.join(STAGE, "reports", "midrelax_20261110.json")
N = int(os.environ.get("STRATA_N", "120"))
SEED = 20261110
MAX_CAND = 3000

# 一个原子查询块：元素（或 #原子序数）+ 若干约束 + 映射号
ATOM = re.compile(r"\[([^\[\]]+)\]")
MAP = re.compile(r":(\d+)")
LEAD = re.compile(r"^(#\d+|\*|[A-Z][a-z]?|[cnosp])")
CHARGE = re.compile(r"^[+-]\d*$|^\+\d+$|^-\d+$")


def _elem_of(tok: str):
    """`C@@H` → C，`nH` → n，`#8` → #8；不是元素记号返回 None。"""
    m = LEAD.match(tok)
    return m.group(1) if m else None


def _split_one(block: str):
    """把一个 [...] 内部拆成 (元素, 电荷, 映射号)；不是原子查询就返回 None。"""
    map_m = MAP.search(block)
    map_tok = ":" + map_m.group(1) if map_m else ""
    body = block[:map_m.start()] if map_m else block
    elem = None
    charge = ""
    for tok in body.split(";"):
        tok = tok.strip()
        if not tok:
            continue
        if elem is None:
            e = _elem_of(tok)
            if e is not None:
                elem = e
                continue
        if CHARGE.match(tok):
            charge = "" if tok in ("+0", "-0") else tok
            continue
        # H 数 / 度数 / 环 / 价态 / 邻居数 / 手性 / 芳香性标记 等：丢掉
    if elem is None:
        return None
    inner = ";".join(x for x in (elem, charge) if x)
    return "[" + inner + map_tok + "]"


def relax_mid(smarts: str) -> str:
    """保留元素、电荷、映射号；丢掉 H 数、度数、环归属。"""
    return ATOM.sub(lambda m: _split_one(m.group(1)) or m.group(0), smarts)


def relax_loose(smarts: str) -> str:
    """只留元素 + 映射号（第 136 轮那一档，作为对照）。"""
    def f(m):
        block = m.group(1)
        map_m = MAP.search(block)
        map_tok = ":" + map_m.group(1) if map_m else ""
        body = block[:map_m.start()] if map_m else block
        for tok in body.split(";"):
            e = _elem_of(tok.strip())
            if e is not None:
                return "[" + e + map_tok + "]"
        return m.group(0)
    return ATOM.sub(f, smarts)


def compile_pool(kind: str):
    seen = set()
    out = {1: [], 2: [], 3: []}
    bad = 0
    with io.open(POOL, encoding="utf-8") as fh:
        for line in fh:
            try:
                d = json.loads(line)
            except Exception:
                continue
            base = d.get("template")
            if not base:
                continue
            if kind == "raw":
                alts = [base]
            elif kind == "mid":
                alts = [relax_mid(base)]
            elif kind == "loose":
                alts = [relax_loose(base)]
            elif kind == "rawmid":
                # 并集：原模板 + 它的中间档放宽版本。用户原来的模板一条不丢，
                # 这才是「放宽能不能补上覆盖」的公平测法（替换式测法会先丢掉原覆盖）。
                alts = [base, relax_mid(base)]
            else:
                raise ValueError(kind)
            for sm in alts:
                if sm in seen:
                    continue
                seen.add(sm)
                try:
                    rxn = AllChem.ReactionFromSmarts(sm)
                except Exception:
                    bad += 1
                    continue
                if rxn is None:
                    bad += 1
                    continue
                a = rxn.GetNumReactantTemplates()
                if a in out:
                    out[a].append((sm, rxn))
    print("pool %-6s unique %6d | arity %s | bad %d"
          % (kind, len(seen), {k: len(v) for k, v in out.items()}, bad), flush=True)
    return out


def run_pool(compiled, mols, want, cap=MAX_CAND):
    from itertools import permutations

    cands = set()
    applied = 0
    for arity, items in compiled.items():
        if arity > len(mols):
            continue
        for _sm, rxn in items:
            for perm in permutations(mols, arity):
                try:
                    outs = rxn.RunReactants(perm)
                except Exception:
                    continue
                if not outs:
                    continue
                applied += 1
                for combo in outs:
                    for m in combo:
                        if m is None:
                            continue
                        try:
                            Chem.SanitizeMol(m)
                        except Exception:
                            continue
                        s = Chem.MolToSmiles(m)
                        if s:
                            cands.add(s)
                if len(cands) > cap:
                    return False, len(cands), applied
    want_k = B.ikey(want)
    found = want in cands or (want_k and want_k in {B.ikey(c) for c in cands})
    return found, len(cands), applied


def pick(recs, sigs, pred, rng, n):
    freq = Counter(s for s in sigs if s is not None)
    pool = [r for r, s in zip(recs, sigs) if s is not None and pred(freq[s])]
    return rng.sample(pool, min(n, len(pool)))


def eval_stratum(name, picked, compiled):
    hits = 0
    cands = []
    skipped = 0
    for r in picked:
        parts, _ = B.substrate_components(str(r["reactants"]))
        mols = []
        for p in parts[:2]:
            smi = B.strip_maps(p)
            m = Chem.MolFromSmiles(smi) if smi else None
            if m is not None:
                mols.append(m)
        want = B.canon(r["product"])
        if not mols or not want:
            skipped += 1
            continue
        found, ncand, _ap = run_pool(compiled, mols, want)
        hits += 1 if found else 0
        cands.append(ncand)
    cands.sort()
    med = cands[len(cands) // 2] if cands else None
    print("  %-9s hits %3d/%3d  median candidates %s"
          % (name, hits, len(picked) - skipped, med), flush=True)
    return hits, len(picked) - skipped, med


def main() -> int:
    t0 = time.time()
    recs = B.build_sample()
    sigs = [(r, B.class_sig(str(r["reactants"]) + ">>" + str(r["product"]))) for r in recs]
    rl = [r for r, s in sigs]
    sg = [s for _r, s in sigs]
    rng = random.Random(SEED)

    strata = {
        "frequent": pick(rl, sg, lambda f: f >= 100, rng, N),
        "mid": pick(rl, sg, lambda f: 10 <= f < 100, rng, N),
        "rare": pick(rl, sg, lambda f: f <= 3, rng, N),
    }
    if os.environ.get("ONLY_RARE", "") in ("1", "true", "yes"):
        strata = {"rare": strata["rare"]}
    print("strata %s (%.0fs)" % ({k: len(v) for k, v in strata.items()}, time.time() - t0),
          flush=True)

    kinds = ("rawmid",) if os.environ.get("ONLY_RARE", "") in ("1", "true", "yes") \
        else ("raw", "mid", "loose", "rawmid")
    pools = {kind: compile_pool(kind) for kind in kinds}
    print("pools compiled (%.0fs)" % (time.time() - t0), flush=True)

    res = {}
    for kind, compiled in pools.items():
        res[kind] = {}
        for name, picked in strata.items():
            hits, n_eff, med = eval_stratum(kind + "/" + name, picked, compiled)
            res[kind][name] = {"hits": hits, "n": n_eff, "median_candidates": med}
        print("pool %s done (%.0fs)" % (kind, time.time() - t0), flush=True)

    payload = {
        "generated_at": __import__("datetime").datetime.now().isoformat(timespec="seconds"),
        "n_per_stratum": N,
        "criterion": "rare >= 25/120 to keep the idea; frequent must not drop by more than 5",
        "result": res,
        "elapsed_s": round(time.time() - t0),
    }
    with io.open(OUT, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(payload, ensure_ascii=False, indent=1))
    print(json.dumps(payload["result"], ensure_ascii=False, indent=1))
    print("wrote", OUT)
    return 0


if __name__ == "__main__":
    sys.exit(main())
