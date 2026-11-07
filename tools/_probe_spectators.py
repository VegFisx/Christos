# -*- coding: utf-8 -*-
# 探针①：三个模板库里，有没有"同一个分子出现在反应两边"的模板（=产物和底物完全相同）？
#   a) 两边有完全相同的分子（去原子映射后规范化一致）
#   b) 前体侧自己是重复分子（如 T >> A.A）
#   c) 整体 no-op（两边完全一样）
import json
import re
import sys

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from rdkit import Chem, RDLogger  # noqa: E402

RDLogger.DisableLog("rdApp.*")


def canon(frag: str) -> str:
    s = re.sub(r":\d+", "", frag)
    m = Chem.MolFromSmiles(s)
    if m is not None:
        return "M|" + Chem.MolToSmiles(m)
    m = Chem.MolFromSmarts(s)
    if m is not None:
        return "S|" + Chem.MolToSmarts(m)
    return "X|" + s


def split_side(side: str):
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


def check(name, items):
    n = both = dup = noop = 0
    ex_both, ex_dup, ex_noop = [], [], []
    for tag, smarts in items:
        if not smarts or ">>" not in smarts:
            continue
        n += 1
        l, r = smarts.split(">>", 1)
        lf = sorted(canon(x) for x in split_side(l))
        rf = sorted(canon(x) for x in split_side(r))
        if set(lf) & set(rf):
            both += 1
            if len(ex_both) < 3:
                ex_both.append((tag, smarts[:96]))
        if len(rf) != len(set(rf)):
            dup += 1
            if len(ex_dup) < 3:
                ex_dup.append((tag, smarts[:96]))
        if lf == rf:
            noop += 1
            if len(ex_noop) < 3:
                ex_noop.append((tag, smarts[:96]))
    print("== %s：%d 条模板" % (name, n))
    print("   两边有相同分子 %d · 前体侧自我重复 %d · 整体 no-op %d" % (both, dup, noop))
    for (t, s) in ex_both:
        print("   [两边同分子] %s %s" % (t, s))
    for (t, s) in ex_dup:
        print("   [前体重复]   %s %s" % (t, s))
    for (t, s) in ex_noop:
        print("   [no-op]      %s %s" % (t, s))
    return n, both, dup, noop


def load_templates_txt():
    p = r"libs\smartreact\data\templates.txt"
    for line in open(p, encoding="utf-8", errors="replace"):
        f = line.rstrip("\n").split("\t")
        if len(f) >= 4:
            yield (f[0] + ":" + f[1], f[3])


def load_jsonl(path, key_candidates):
    for i, line in enumerate(open(path, encoding="utf-8")):
        line = line.strip()
        if not line:
            continue
        r = json.loads(line)
        smarts = ""
        for k in key_candidates:
            if r.get(k):
                smarts = str(r[k])
                break
        yield (str(i), smarts)


print("文件内方向不做区分（两边对称检查）")
check("SmartReact 正向模板 templates.txt", load_templates_txt())
print()
check("挖矿 3 组分正向模板 mined_forward_templates_3c.jsonl",
      load_jsonl(r"reports\mined_forward_templates_3c.jsonl", ("template", "smarts")))
print()
check("rdchiral 逆模板 retro_templates_clustered.jsonl",
      load_jsonl(r"reports\retro_templates_clustered.jsonl", ("template", "smarts")))
