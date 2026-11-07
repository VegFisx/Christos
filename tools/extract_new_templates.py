# -*- coding: utf-8 -*-
r"""★ 补"零覆盖"反应类型：从 ORD 抽新模板，并在【独立测试集】上验证 ★★

务必避免今天的第一个错误（自指的 100%）：
  模板从 train 抽，只在 test（互不相交）上验收。

流程：
  1. 抽样 ORD 干净映射反应（恰好 2 个组分贡献原子到产物）
  2. 按反应 id 的哈希 50/50 分 train / test
  3. 只用 train 判定哪些反应中心是"零覆盖"（现有 9770 模板一条都不成功）
  4. 在 train 上用 RDChiral 抽这些零覆盖中心的模板（★注意转正向★）
  5. 在 test 上：只看现有库漏掉的、且属于零覆盖中心的反应，看新模板能否复现
  6. 同时测假阳性：把新模板用到【其它】反应中心的 test 反应上，看会不会乱产出

用法: python extract_new_templates.py [抽样数]
"""
import hashlib
import json
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

STAGE = Path(r"D:\ProgramData\DSHNS\chemreact-staging")
sys.path.insert(0, str(STAGE / "libs"))

import duckdb  # noqa: E402
from rdkit import Chem, RDLogger  # noqa: E402
from rdkit.Chem import rdChemReactions  # noqa: E402
from ord_schema.proto import reaction_pb2  # noqa: E402
from smartreact import ReactionEnumerator  # noqa: E402
from rdchiral.template_extractor import extract_from_reaction  # noqa: E402

RDLogger.DisableLog("rdApp.*")

N = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
BIG = STAGE / "ord-data" / "data" / "11" / \
    "ord_dataset-1158e351757f315b93cbcbe7bc55f38e.parquet"
OUT = STAGE / "reports" / "new_templates_pilot.json"
OUT.parent.mkdir(parents=True, exist_ok=True)


def split_rxn(cx):
    body = cx[:cx.index("|")] if "|" in cx else cx
    parts = [p for p in body.split(">") if p.strip()]
    if len(parts) == 3:
        return parts[0], parts[1], parts[2]
    if len(parts) == 2:
        return parts[0], "", parts[1]
    return None, None, None


def canon_nomap(smi):
    try:
        m = Chem.MolFromSmiles(smi)
        if m is None:
            return None
        for a in m.GetAtoms():
            a.SetAtomMapNum(0)
        return Chem.MolToSmiles(m)
    except Exception:
        return None


def bond_set(mol):
    out = set()
    for b in mol.GetBonds():
        m1, m2 = b.GetBeginAtom().GetAtomMapNum(), b.GetEndAtom().GetAtomMapNum()
        if m1 and m2:
            out.add((min(m1, m2), max(m1, m2)))
    return out


def is_carbonyl_c(a):
    if a.GetSymbol() != "C":
        return False
    for b in a.GetBonds():
        o = b.GetOtherAtom(a)
        if o.GetSymbol() in ("O", "N", "S") and b.GetBondTypeAsDouble() == 2.0:
            return True
    return False


def adesc(a):
    sym = a.GetSymbol()
    if sym == "N":
        if a.GetIsAromatic():
            return "唑N"
        if any(is_carbonyl_c(nb) for nb in a.GetNeighbors()):
            return "酰胺N"
        hn = sum(1 for nb in a.GetNeighbors() if nb.GetSymbol() == "H")
        return f"胺N({'NH2' if hn >= 2 else 'NH' if hn == 1 else 'N'})"
    if sym == "O":
        if a.GetIsAromatic():
            return "酚O/芳醚O"
        return "醚/酯O" if sum(1 for nb in a.GetNeighbors()
                            if nb.GetSymbol() == "C") >= 2 else "羟基O"
    s = sym
    if a.GetIsAromatic():
        s += "ar"
    elif a.IsInRing():
        s += "环"
    if is_carbonyl_c(a):
        s += "=O"
    het = sum(1 for nb in a.GetNeighbors() if nb.GetSymbol() not in ("C", "H"))
    if het:
        s += f"{min(het,3)}杂"
    return s


# ---------------- 1. 抽样并整理 ----------------
con = duckdb.connect()
con.execute("SET memory_limit='1500MB'")
con.execute("SET threads=2")
rows = con.execute(
    f"SELECT reaction FROM read_parquet('{BIG.as_posix()}') USING SAMPLE {N} ROWS"
).fetchall()
print(f"抽样 {len(rows)} 条")

recs = []
seen = set()
skip = Counter()
for (blob,) in rows:
    rxn = reaction_pb2.Reaction()
    try:
        rxn.ParseFromString(blob)
    except Exception:
        continue
    cx = next((i.value for i in rxn.identifiers
               if i.type == reaction_pb2.ReactionIdentifier.REACTION_CXSMILES), None)
    if cx is None:
        continue
    lhs, agents, rhs = split_rxn(cx)
    if not lhs or not rhs:
        continue
    pm = Chem.MolFromSmiles(rhs)
    if pm is None:
        continue
    pmaps = {a.GetAtomMapNum() for a in pm.GetAtoms() if a.GetAtomMapNum() > 0}
    if not pmaps:
        continue
    product = canon_nomap(rhs)
    if product is None:
        continue

    # ★ 必须同时保留【带映射】的原始串（给 RDChiral）和【去映射】的规范串（给枚举器）
    keep_raw, keep_canon, left_bonds = [], [], set()
    for s in (x for x in lhs.split(".") if x):
        m = Chem.MolFromSmiles(s)
        if m is None:
            continue
        maps = {a.GetAtomMapNum() for a in m.GetAtoms() if a.GetAtomMapNum() > 0}
        if maps and len(maps & pmaps) / len(maps) > 0.5:
            cs = canon_nomap(s)
            if cs:
                keep_raw.append(s)
                keep_canon.append(cs)
        left_bonds |= bond_set(m)
    if len(keep_canon) != 2:
        skip[f"组分={len(keep_canon)}"] += 1
        continue
    r1, r2 = sorted(keep_canon)
    if (r1, r2, product) in seen:
        continue
    seen.add((r1, r2, product))

    formed = bond_set(pm) - left_bonds
    labs = []
    for pair in formed:
        a1 = next((a for a in pm.GetAtoms() if a.GetAtomMapNum() == pair[0]), None)
        a2 = next((a for a in pm.GetAtoms() if a.GetAtomMapNum() == pair[1]), None)
        if a1 and a2:
            labs.append(" - ".join(sorted([adesc(a1), adesc(a2)])))
    label = "(无成键)" if not labs else (labs[0] if len(labs) == 1 else f"(多键){labs[0]}")

    hid = hashlib.md5((r1 + "|" + r2 + "|" + product).encode()).hexdigest()
    split = "train" if int(hid[:8], 16) % 2 == 0 else "test"
    recs.append({"r1": r1, "r2": r2, "product": product, "label": label,
                 "split": split, "reactants_mapped": ".".join(keep_raw),
                 "products_mapped": rhs, "agents": agents or ""})

print(f"可用 {len(recs)} 条（去重后）   跳过: {dict(skip)}")
tr = [r for r in recs if r["split"] == "train"]
te = [r for r in recs if r["split"] == "test"]
print(f"train {len(tr)}   test {len(te)}\n")

# ---------------- 2. 用现有库在 train 上找"零覆盖"中心 ----------------
enum = ReactionEnumerator()
train_stat = defaultdict(lambda: [0, 0])   # label -> [cases, hits]
t0 = time.time()
for r in tr:
    try:
        res = enum.enumerate_pair(r["r1"], r["r2"])
    except Exception:
        continue
    train_stat[r["label"]][0] += 1
    for x in res:
        for p in x.products:
            if canon_nomap(p) == r["product"]:
                train_stat[r["label"]][1] += 1
                break
        else:
            continue
        break
print(f"现有库在 train 上跑完，耗时 {time.time()-t0:.0f}s\n")

print("=" * 92)
print("train 上各反应中心的现有库覆盖率")
print("=" * 92)
zero_labels = {}
for lab, (c, h) in sorted(train_stat.items(), key=lambda kv: -kv[1][0]):
    if c < 5:
        continue
    print(f"   {h:>4}/{c:<4} ({h/c*100:5.1f}%)  {lab}")
    if h == 0:
        zero_labels[lab] = c
print()
print(f"★ 判定为零覆盖的反应中心 {len(zero_labels)} 个，合计 {sum(zero_labels.values())} 条:")
for lab, c in sorted(zero_labels.items(), key=lambda kv: -kv[1]):
    print(f"      {c:>4} 条  {lab}")

# ---------------- 3. 在 train 上抽模板 ----------------
print()
print("=" * 92)
print("从 train 的零覆盖中心抽模板（RDChiral）")
print("=" * 92)
tmpl_hits = Counter()
tmpl_of = {}
n_try = n_ok = n_intra = n_dimer = 0
for r in tr:
    if r["label"] not in zero_labels:
        continue
    n_try += 1
    try:
        out = extract_from_reaction({
            "reactants": r["reactants_mapped"],
            "reagents": r["agents"],
            "products": r["products_mapped"],
            "_id": "x",
        })
    except Exception:
        continue
    if not out or "reaction_smarts" not in out:
        continue
    if out.get("intra_only"):
        n_intra += 1
        continue
    if out.get("dimer_only"):
        n_dimer += 1
        continue
    # ★ RDChiral 输出是逆合成方向（产物>>底物），正向要交换 ★
    rs = out["reaction_smarts"]
    if ">>" not in rs:
        continue
    a, b = rs.split(">>", 1)
    fwd = b + ">>" + a
    if fwd not in tmpl_of:
        tmpl_of[fwd] = r["label"]
    tmpl_hits[fwd] += 1
    n_ok += 1

print(f"尝试 {n_try} 条，抽出模板 {n_ok} 次，去重后 {len(tmpl_of)} 个")
print(f"（跳过 intra_only {n_intra}，dimer_only {n_dimer}）")

# 按覆盖案例数排序
print("\n覆盖面最大的 12 个新模板:")
for t, c in tmpl_hits.most_common(12):
    print(f"   {c:>4} 例  [{tmpl_of[t]}]")
    print(f"         {t[:170]}")

# ---------------- 4. 在 test 上验收 ----------------
print()
print("=" * 92)
print("★ 在【独立测试集】上验收")
print("=" * 92)
test_stat = defaultdict(lambda: [0, 0])
for r in te:
    try:
        res = enum.enumerate_pair(r["r1"], r["r2"])
    except Exception:
        continue
    test_stat[r["label"]][0] += 1
    for x in res:
        for p in x.products:
            if canon_nomap(p) == r["product"]:
                test_stat[r["label"]][1] += 1
                break
        else:
            continue
        break

def generalize_smarts(smarts):
    r"""把模板原子剥到只剩 元素+芳香性+电荷+映射号，去掉 H数/D数/环融合等细节。
    目的：解决 rdchiral radius=1 模板把底物骨架写死导致的过拟合。"""
    try:
        rx = rdChemReactions.ReactionFromSmarts(smarts)
    except Exception:
        return None
    if rx is None:
        return None

    def gen(mol):
        if mol is None:
            return None
        rw = Chem.RWMol()
        idx = {}
        for a in mol.GetAtoms():
            na = Chem.Atom(a.GetAtomicNum())
            na.SetIsAromatic(a.GetIsAromatic())
            na.SetFormalCharge(a.GetFormalCharge())
            na.SetAtomMapNum(a.GetAtomMapNum())
            idx[a.GetIdx()] = rw.AddAtom(na)
        for b in mol.GetBonds():
            rw.AddBond(idx[b.GetBeginAtomIdx()], idx[b.GetEndAtomIdx()], b.GetBondType())
        m = rw.GetMol()
        try:
            Chem.SanitizeMol(m)
        except Exception:
            return None
        try:
            return Chem.MolToSmarts(m)
        except Exception:
            return None

    rs = [gen(rx.GetReactantTemplate(i)) for i in range(rx.GetNumReactantTemplates())]
    ps = [gen(rx.GetProductTemplate(i)) for i in range(rx.GetNumProductTemplates())]
    if any(x is None for x in rs + ps) or not rs or not ps:
        return None
    return ".".join(rs) + ">>" + ".".join(ps)


# 编译模板（只保留覆盖 >= 2 例的，避免一次性过拟合模板）
compiled = []
compiled_gen = []
skipped_thin = 0
n_gen_fail = 0
for t, lab in tmpl_of.items():
    if tmpl_hits[t] < 2:
        skipped_thin += 1
        continue
    try:
        rx = rdChemReactions.ReactionFromSmarts(t)
        if rx is None or rx.GetNumReactantTemplates() != 2:
            continue
        compiled.append((t, lab, rx))
    except Exception:
        continue
    g = generalize_smarts(t)
    if g:
        try:
            grx = rdChemReactions.ReactionFromSmarts(g)
            if grx is not None and grx.GetNumReactantTemplates() == 2:
                compiled_gen.append((g, lab, grx))
            else:
                n_gen_fail += 1
        except Exception:
            n_gen_fail += 1
    else:
        n_gen_fail += 1
print(f"可编译的正向模板 {len(compiled)} 个（另有 {skipped_thin} 个只覆盖 1 例，未用）")
print(f"泛化版本模板 {len(compiled_gen)} 个（泛化失败 {n_gen_fail}）")

apply_cache = {}


def apply_templates(r1, r2, tmpl_list, tag):
    """返回 (产出集合, 命中的模板集合)。tag 用于区分缓存。"""
    key = (tag, r1, r2)
    if key in apply_cache:
        return apply_cache[key]
    m1, m2 = Chem.MolFromSmiles(r1), Chem.MolFromSmiles(r2)
    got, used = set(), set()
    if m1 is None or m2 is None:
        apply_cache[key] = (got, used)
        return got, used
    for t, lab, rx in tmpl_list:
        try:
            outs = rx.RunReactants((m1, m2))
        except Exception:
            continue
        for tup in outs:
            for pmol in tup:
                try:
                    Chem.SanitizeMol(pmol)
                except Exception:
                    continue
                cp = canon_nomap(Chem.MolToSmiles(pmol))
                if cp:
                    got.add(cp)
                    used.add(t)
    apply_cache[key] = (got, used)
    return got, used


# 目标：test 上属于零覆盖中心、且现有库漏掉的反应
targets = [r for r in te if r["label"] in zero_labels]
t0 = time.time()
res_raw = Counter()
res_gen = Counter()
newly_raw = newly_gen = 0
for r in targets:
    got, _ = apply_templates(r["r1"], r["r2"], compiled, "raw")
    if r["product"] in got:
        newly_raw += 1
        res_raw[r["label"]] += 1
    gotg, _ = apply_templates(r["r1"], r["r2"], compiled_gen, "gen")
    if r["product"] in gotg:
        newly_gen += 1
        res_gen[r["label"]] += 1

print(f"test 中属于零覆盖中心的反应 {len(targets)} 条，耗时 {time.time()-t0:.0f}s")
print()
print("   ★ 原始模板（rdchiral radius=1） 复现 "
      f"{newly_raw} 条 ({newly_raw/len(targets)*100 if targets else 0:.1f}%)")
print("   ★ 泛化模板（只留元素+芳香性+电荷+映射号） 复现 "
      f"{newly_gen} 条 ({newly_gen/len(targets)*100 if targets else 0:.1f}%)")
print()
print("   按反应中心（泛化后）:")
for lab, c in res_gen.most_common():
    tot = sum(1 for r in targets if r["label"] == lab)
    r0 = res_raw.get(lab, 0)
    print(f"      {c:>4}/{tot:<4} ({c/tot*100:5.1f}%)  [原始 {r0}]  {lab}")

# ---------------- 5. 假阳性检查 ----------------
print()
print("=" * 92)
print("★ 假阳性检查：把新模板用到【其它】反应中心的 test 反应上")
print("=" * 92)
others = [r for r in te if r["label"] not in zero_labels]
import random
random.seed(0)
fp_sample = others if len(others) <= 500 else random.sample(others, 500)
spurious = spurious_gen = 0
checked = 0
produced_examples = []
for r in fp_sample:
    got, _ = apply_templates(r["r1"], r["r2"], compiled, "raw")
    ggot, _ = apply_templates(r["r1"], r["r2"], compiled_gen, "gen")
    checked += 1
    if got:
        spurious += 1
    if ggot:
        spurious_gen += 1
        if len(produced_examples) < 3:
            produced_examples.append({"reactants": [r["r1"], r["r2"]],
                                      "expected": r["product"],
                                      "produced": list(ggot)[:3]})
print(f"   检查 {checked} 条非目标反应：")
print(f"      原始模板【有产出】 {spurious} 条 ({spurious/checked*100 if checked else 0:.1f}%)")
print(f"      泛化模板【有产出】 {spurious_gen} 条 "
      f"({spurious_gen/checked*100 if checked else 0:.1f}%)")
print(f"   （有产出 ≠ 错，但产出率过高说明模板过于宽松）")
for e in produced_examples:
    print(f"      底物 {e['reactants']}")
    print(f"      实际产物 {e['expected']}")
    print(f"      泛化模板产出 {e['produced']}")

OUT.write_text(json.dumps({
    "sampled": len(rows), "recs": len(recs), "train": len(tr), "test": len(te),
    "zero_labels": zero_labels,
    "train_stat": {k: v for k, v in train_stat.items()},
    "test_stat": {k: v for k, v in test_stat.items()},
    "n_templates": len(tmpl_of),
    "templates": {t: {"label": lab, "cases": tmpl_hits[t]} for t, lab in tmpl_of.items()},
    "test_targets": len(targets),
    "newly_covered_raw": newly_raw, "newly_covered_gen": newly_gen,
    "false_positive_probe": {"checked": checked, "produced_raw": spurious,
                             "produced_gen": spurious_gen},
}, ensure_ascii=False, indent=1), encoding="utf-8")
print(f"\n已存: {OUT}")

enum.close()
con.close()
