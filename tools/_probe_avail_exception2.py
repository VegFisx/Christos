# -*- coding: utf-8 -*-
# 第四十三轮探针 v2：可得性例外 —— 全量终止集合（COCONUT + tcm.db + 砌块）下的影响，
# 并把所有 R1 (目标,前体) 对落盘（reports/_dirty8_r1_pairs.jsonl），以后免重算。
import csv
import json
import sys
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

from rdkit import Chem, RDLogger                       # noqa: E402
import retro_search as rs                              # noqa: E402

RDLogger.DisableLog("rdApp.*")


def load_targets(n):
    seen, out = set(), []
    with open(STAGE / "reports" / "query_inventory_paths.csv",
              encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            smi = str(row.get("product_smiles") or "").strip()
            if not smi or smi in seen:
                continue
            m = Chem.MolFromSmiles(smi)
            if m is None:
                continue
            seen.add(smi)
            out.append(Chem.MolToSmiles(m))
            if len(out) >= n:
                break
    return out


targets = load_targets(56)
tmpl = rs.load_rdchiral_templates()
by_idx = {i: t for i, t in enumerate(tmpl, 1)}

print("加载终止集合（COCONUT + tcm.db(只读回退) + 砌块）...", flush=True)
av = rs.load_available()
bf, bs = rs.load_purchasable_blocks()
eng = rs.RetroSearch([], av, blocks_full=bf, blocks_skel=bs)
print("  可得：旧集合 %d / 砌块 full %d / 骨架 %d" % (len(av), len(bf), len(bs)), flush=True)

n_cut = 0
rows = []
for i in [451, 452, 1208, 1041, 1042, 1161, 88, 954]:
    t = by_idx.get(i)
    if t is None:
        continue
    for tgt in targets:
        try:
            outs = t.rxn.RunReactants((Chem.MolFromSmiles(tgt),))
        except Exception:
            continue
        for tup in outs:
            prec = tuple(rs.canon(Chem.MolToSmiles(p)) for p in tup if p is not None)
            prec = tuple(p for p in prec if p)
            if not prec:
                continue
            n_cut += 1
            ok, why = rs.step_usability(tgt, prec)
            if ok or not why.startswith("R1"):
                continue
            # R1 切断：找出"触发 R1"的前体（缓存已热，单前体重算=缓存命中）
            trig = []
            for p in prec:
                ok1, why1 = rs.step_usability(tgt, (p,))
                if not ok1 and why1.startswith("R1"):
                    trig.append(p)
            avail = []
            for p in trig:
                label = None
                k = rs.ik(p)
                if k:
                    label = av.get(k)
                if label is None and k:
                    label = bf.get(k)
                avail.append(label)
            rows.append({"idx": i, "target": tgt, "precursors": list(prec),
                         "r1_triggerers": trig, "available": avail})

out_p = STAGE / "reports" / "_dirty8_r1_pairs.jsonl"
with open(out_p, "w", encoding="utf-8") as f:
    for r in rows:
        f.write(json.dumps(r, ensure_ascii=False) + "\n")

n_r1 = len(rows)
n_pass = sum(1 for r in rows if any(x is not None for x in r["available"]))
n_pass_coco = sum(1 for r in rows if any(x and "tcm.db" not in x for x in r["available"]))
n_pass_tcm = sum(1 for r in rows if any(x and "tcm.db" in x for x in r["available"]))
src = Counter()
for r in rows:
    for x in r["available"]:
        if x:
            src[x.split(":")[0]] += 1
print("== 全量终止集合下的可得性例外 ==")
print("  切断总数 %d · R1 切断 %d" % (n_cut, n_r1))
print("  R1 中触发前体【可得】的：%d 条（COCONUT/砌块 %d · tcm.db %d）"
      % (n_pass, n_pass_coco, n_pass_tcm))
print("  可得来源计数:", dict(src))
print("  明细 -> %s（%d 条）" % (out_p.name, len(rows)))
print("  USTAT:", {k: v for k, v in rs.USTAT.items() if v})
