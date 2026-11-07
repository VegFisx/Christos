# -*- coding: utf-8 -*-
# 第四十三轮探针：可得性例外（「只在前体不可得时才判假」）的实际影响
#  ① 找一条"现在会判 R1"的具体 (目标,前体) 对（做池问答演示用）
#  ② dirty-8 × 56 目标：旧判定 vs 新判定（available_fn = 引擎 is_available）逐一切断对照
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

print("加载终止集合（COCONUT 索引 + tcm.db(只读) + 砌块）...", flush=True)
av = rs.load_available()
bf, bs = rs.load_purchasable_blocks()
eng = rs.RetroSearch([], av, blocks_full=bf, blocks_skel=bs)
print("  可得分子：%d (旧集合) / 砌块 full %d / 骨架 %d" % (len(av), len(bf), len(bs)),
      flush=True)

DIRTY = [451, 452, 1208, 1041, 1042, 1161, 88, 954]
stat = {"old_usable": 0, "old_R1": 0, "old_R2": 0, "old_other": 0,
        "new_usable": 0, "new_R1": 0, "new_R2": 0, "new_other": 0,
        "pass_avail": 0}
demo = None
rows_out = []
for i in DIRTY:
    t = by_idx.get(i)
    if t is None:
        continue
    for tgt in targets:
        t_hac = Chem.MolFromSmiles(tgt).GetNumHeavyAtoms()
        try:
            outs = t.rxn.RunReactants((Chem.MolFromSmiles(tgt),))
        except Exception:
            continue
        for tup in outs:
            prec = tuple(rs.canon(Chem.MolToSmiles(p)) for p in tup if p is not None)
            prec = tuple(p for p in prec if p)
            if not prec:
                continue
            ok_old, why_old = rs.step_usability(tgt, prec)
            n_pass_before = rs.USTAT.get("r1_pass_available", 0)
            ok_new, why_new = rs.step_usability(tgt, prec, available_fn=eng.is_available)
            passed = rs.USTAT.get("r1_pass_available", 0) > n_pass_before
            # 旧口径归类
            if ok_old:
                stat["old_usable"] += 1
            elif why_old.startswith("R1"):
                stat["old_R1"] += 1
                if demo is None:
                    demo = (i, tgt, prec)
            elif why_old.startswith("R2"):
                stat["old_R2"] += 1
            else:
                stat["old_other"] += 1
            # 新口径归类
            if ok_new:
                stat["new_usable"] += 1
            elif why_new.startswith("R1"):
                stat["new_R1"] += 1
            elif why_new.startswith("R2"):
                stat["new_R2"] += 1
            else:
                stat["new_other"] += 1
            if passed:
                stat["pass_avail"] += 1
                rows_out.append({"idx": i, "target": tgt, "precursors": list(prec)})

print("== dirty-8 全部切断：旧判定 vs 新判定 ==")
print("  旧：可用 %d · R1 %d · R2 %d · 其他 %d"
      % (stat["old_usable"], stat["old_R1"], stat["old_R2"], stat["old_other"]))
print("  新：可用 %d · R1 %d · R2 %d · 其他 %d"
      % (stat["new_usable"], stat["new_R1"], stat["new_R2"], stat["new_other"]))
print("  ★ 被「前体可得」放行：%d 条" % stat["pass_avail"])
print("  USTAT:", {k: v for k, v in rs.USTAT.items() if v})
out_p = STAGE / "reports" / "_dirty8_avail_passed.jsonl"
with open(out_p, "w", encoding="utf-8") as f:
    for r in rows_out:
        f.write(json.dumps(r, ensure_ascii=False) + "\n")
print("  放行明细 -> %s（%d 条）" % (out_p.name, len(rows_out)))
if demo:
    i, tgt, prec = demo
    print("== 演示对（idx %d）==" % i)
    print("  目标 %s" % tgt)
    for p in prec:
        print("  前体 %s" % p)
    with open(STAGE / "reports" / "_avail_demo_pair.txt", "w", encoding="utf-8") as f:
        f.write("target\t%s\n" % tgt)
        for p in prec:
            f.write("precursor\t%s\n" % p)
