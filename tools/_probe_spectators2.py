# -*- coding: utf-8 -*-
# 探针②（严格版）：判断"同一个分子（同一批映射原子）是否原样出现在反应两边"。
#   严格 = 保留原子映射号比较（真·同一分子）；宽松 = 抹掉映射号（可能把"同位占位"误算）。
#   对严格命中的逆模板，再做"应用到 56 个目标"的实测：会不会产出 目标==前体 的自切断？
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


def canon_map(frag):
    """保留映射号的规范化；解析失败返回 None。"""
    m = Chem.MolFromSmiles(frag)
    return Chem.MolToSmiles(m) if m is not None else None


def canon_loose(frag):
    import re
    s = re.sub(r":\d+", "", frag)
    m = Chem.MolFromSmiles(s)
    if m is not None:
        return "M|" + Chem.MolToSmiles(m)
    m = Chem.MolFromSmarts(s)
    return ("S|" + Chem.MolToSmarts(m)) if m is not None else "X|" + s


def split_side(side):
    out, depth, cur = [], 0, []
    for ch in side:
        if ch in "([":
            depth += 1
        elif ch in ")]":
            depth -= 1
        if ch == "." and depth == 0:
            out.append("".join(cur).strip())
            cur = []
        else:
            cur.append(ch)
    out.append("".join(cur).strip())
    return [x for x in out if x]


def flags(smarts):
    l, r = smarts.split(">>", 1)
    lfs, rfs = split_side(l), split_side(r)
    ls = [canon_map(x) for x in lfs]
    rs_ = [canon_map(x) for x in rfs]
    ls_ok = [x for x in ls if x]
    rs_ok = [x for x in rs_ if x]
    strict_both = bool(set(ls_ok) & set(rs_ok))
    strict_noop = (len(ls_ok) == len(ls) and len(rs_ok) == len(rs_)
                   and sorted(ls_ok) == sorted(rs_ok))
    strict_dup = len(rs_ok) != len(set(rs_ok))
    ll = [canon_loose(x) for x in lfs]
    rl = [canon_loose(x) for x in rfs]
    loose_both = bool(set(ll) & set(rl))
    return strict_both, strict_noop, strict_dup, loose_both, lfs, rfs


print("== 逆模板库（rdchiral，3,228 条）==")
tmpl = rs.load_rdchiral_templates()
strict_list, noop_list, dup_list = [], [], []
n_loose = 0
for i, t in enumerate(tmpl, 1):
    sb, sn, sd, lb, _, _ = flags(t.smarts)
    if sb:
        strict_list.append((i, t.smarts))
    if sn:
        noop_list.append((i, t.smarts))
    if sd:
        dup_list.append((i, t.smarts))
    if lb:
        n_loose += 1
print("严格：两边同分子 %d 条（其中整体 no-op %d）· 前体严格重复 %d 条 · 宽松同分子 %d 条"
      % (len(strict_list), len(noop_list), len(dup_list), n_loose))
rows = [json.loads(x) for x in open(STAGE / "reports" / "retro_template_audit_r41.jsonl",
                                    encoding="utf-8") if x.strip()]
hit_idx = {r["idx"] for r in rows}
flag_idx = {i for i, _ in strict_list} | {i for i, _ in noop_list} | {i for i, _ in dup_list}
print("其中出现在体检'有命中'名单（86 条）里的：%d 条 -> %s"
      % (len(flag_idx & hit_idx), sorted(flag_idx & hit_idx)))
for i, s in strict_list[:8]:
    print("  [严格同分子] idx %4d %s" % (i, s[:100]))
for i, s in noop_list:
    print("  [no-op    ] idx %4d %s" % (i, s[:100]))

print()
print("== 实测：把严格命中的模板套到 56 个目标上，会产出什么？==")


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
by_idx = {i: t for i, t in enumerate(tmpl, 1)}
n_app = n_selfcut = n_dupcut = 0
ex_self = []
for i in sorted(flag_idx):
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
            n_app += 1
            if tgt in prec:
                n_selfcut += 1
                if len(ex_self) < 4:
                    ex_self.append((i, tgt, prec))
            if len(prec) != len(set(prec)):
                n_dupcut += 1
print("命中模板共尝试出 %d 个切断；其中【前体 == 目标】%d 个 · 【前体自我重复】%d 个"
      % (n_app, n_selfcut, n_dupcut))
for i, tgt, prec in ex_self:
    print("  e.g. idx %d 目标=%s" % (i, tgt[:60]))
    print("       前体=%s" % " | ".join(p[:60] for p in prec))
