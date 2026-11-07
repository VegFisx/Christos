# -*- coding: utf-8 -*-
# 第四十三轮探针④：把挖矿 3 组分模板里的"原样穿过分子"剥掉（两边同时删），
# 看 ① 多少条剥完还能编译成干净的二组分模板；② 在甘草成分两两组合上能触发多少切断。
# 输出：reports/_strip_spectators_probe.jsonl + 屏幕摘要。只分析，不改任何库文件。
import csv
import json
import re
import sys
from collections import Counter
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

MINED = STAGE / "reports" / "mined_forward_templates_3c.jsonl"
OUT = STAGE / "reports" / "_strip_spectators_probe.jsonl"
CSV = STAGE / "reports" / "query_inventory_paths.csv"


def _split(side):
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


def _key(frag):
    s = re.sub(r":\d+", "", frag)
    m = Chem.MolFromSmiles(s)
    if m is not None:
        return "M|" + Chem.MolToSmiles(m)
    m = Chem.MolFromSmarts(s)
    return ("S|" + Chem.MolToSmarts(m)) if m is not None else "X|" + s


def _unit(frag):
    return (frozenset(int(x) for x in re.findall(r":(\d+)", frag)), _key(frag))


def strip_shared(lf, rf):
    """把两侧都出现的（映射级相同）片段各删 min(计数) 个，返回 (kept_l, kept_r, 去掉的单元)。"""
    cl, cr = Counter(_unit(f) for f in lf), Counter(_unit(f) for f in rf)
    shared = cl & cr
    if not shared:
        return lf, rf, {"dropped_l": [], "dropped_r": []}

    def _mark(frags):
        left = Counter(shared)
        keeps, drops = [], []
        for idx, f in enumerate(frags):
            u = _unit(f)
            if left.get(u, 0) > 0:
                left[u] -= 1
                drops.append(idx)
            else:
                keeps.append(idx)
        return keeps, drops

    keep_l, drop_l = _mark(lf)
    keep_r, drop_r = _mark(rf)
    return ([lf[k] for k in keep_l], [rf[k] for k in keep_r],
            {"dropped_l": [lf[k] for k in drop_l], "dropped_r": [rf[k] for k in drop_r]})


def main():
    rows = []
    n_total = n_shared = n_ok = n_fail = 0
    spectator_counter = Counter()
    comp_templates = []
    for line_no, line in enumerate(open(MINED, encoding="utf-8")):
        line = line.strip()
        if not line:
            continue
        n_total += 1
        r = json.loads(line)
        sm = r.get("template") or r.get("smarts") or ""
        if ">>" not in sm:
            continue
        l, rr = sm.split(">>", 1)
        lf, rf = _split(l), _split(rr)
        units_l, units_r = {_unit(f) for f in lf}, {_unit(f) for f in rf}
        if not (units_l & units_r):
            continue
        n_shared += 1
        kept_l, kept_r, drop = strip_shared(lf, rf)
        new_smarts = ".".join(kept_l) + ">>" + ".".join(kept_r)
        ok = False
        n_r = n_p = -1
        try:
            rx = rdChemReactions.ReactionFromSmarts(new_smarts)
            if rx is not None:
                n_r, n_p = rx.GetNumReactantTemplates(), rx.GetNumProductTemplates()
                ok = (n_r >= 1 and n_p >= 1 and n_r <= 2)
        except Exception:
            rx = None
        for f in drop["dropped_l"]:
            spectator_counter[_key(f)] += 1
        if ok:
            n_ok += 1
            comp_templates.append((line_no, new_smarts, rx))
        else:
            n_fail += 1
        rows.append({"line": line_no, "spectators": drop["dropped_l"],
                     "stripped_smarts": new_smarts, "compiled": ok,
                     "n_reactants": n_r, "n_products": n_p})

    # 甘草成分对：从台账 source_smiles 取（不碰数据库）
    mols = []
    if CSV.exists():
        seen = set()
        with open(CSV, encoding="utf-8-sig", newline="") as f:
            for row in csv.DictReader(f):
                smi = str(row.get("source_smiles") or "").strip()
                m = Chem.MolFromSmiles(smi) if smi else None
                if m is None:
                    continue
                c = Chem.MolToSmiles(m)
                if c not in seen:
                    seen.add(c)
                    mols.append(m)
    n_fire = 0
    n_cuts = 0
    for _, smarts, rx in comp_templates:
        fired = 0
        for i in range(len(mols)):
            for j in range(len(mols)):
                if i == j:
                    continue
                try:
                    outs = rx.RunReactants((mols[i], mols[j]))
                except Exception:
                    continue
                fired += len(outs)
        if fired:
            n_fire += 1
            n_cuts += fired

    with open(OUT, "w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    print("== 剥旁观者：可行性 ==")
    print("mined_3c 总 %d 条 · 有'原样穿过'的 %d 条" % (n_total, n_shared))
    print("剥掉后能编译成干净模板的：%d 条（失败 %d 条）" % (n_ok, n_fail))
    print("被剥掉的旁观分子 top：", spectator_counter.most_common(8))
    print("== 剥后模板在甘草成分（%d 个）两两组合上的触发 ==" % len(mols))
    print("触发过的模板 %d 条 · 产出切断 %d 个" % (n_fire, n_cuts))
    print("明细 -> %s" % OUT.name)


if __name__ == "__main__":
    main()
