# -*- coding: utf-8 -*-
# 探针③：把"两边同分子"的候选全部拉出来人眼确认（不靠自动判据下结论）
#   ① 逆模板库 raw 文件的宽松命中 -> 全文 + 是否在编译集里（tid 对照）
#   ② 挖矿 3 组分正向模板 -> 命中实例的"同分子片段"TOP 频次（催化剂候选名单）
import json
import re
import sys
from collections import Counter

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from rdkit import Chem, RDLogger  # noqa: E402

RDLogger.DisableLog("rdApp.*")


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


print("== ① 逆模板 raw（3,228 行）：两边同分子候选全文，及是否在编译集 ==")
raw = []
for i, line in enumerate(open(r"reports\retro_templates_clustered.jsonl", encoding="utf-8")):
    line = line.strip()
    if line:
        raw.append((i, json.loads(line)["template"]))
kept = set()
import sys as _sys
_sys.path.insert(0, r"tools")
import retro_search as rs  # noqa: E402
for t in rs.load_rdchiral_templates():
    kept.add(t.tid)
shown = 0
for i, sm in raw:
    l, r = sm.split(">>", 1)
    lk = {_key(x) for x in _split(l)}
    rk = {_key(x) for x in _split(r)}
    inter = lk & rk
    if inter:
        shown += 1
        if shown <= 14:
            print("行%4d 编译集内=%s 交集=%s" % (i, "是" if i in kept else "否(被跳过)", sorted(inter)))
            print("        %s" % sm[:130])
print("候选合计 %d 行" % shown)

print()
print("== ② 挖矿 3 组分正向模板：'两边同分子'的片段 TOP 频次 ==")
top = Counter()
n_tmpl = 0
examples = []
for line in open(r"reports\mined_forward_templates_3c.jsonl", encoding="utf-8"):
    line = line.strip()
    if not line:
        continue
    r = json.loads(line)
    sm = r.get("template") or r.get("smarts") or ""
    if ">>" not in sm:
        continue
    n_tmpl += 1
    l, rr = sm.split(">>", 1)
    lk = {_key(x) for x in _split(l)}
    rk = {_key(x) for x in _split(rr)}
    inter = lk & rk
    if inter:
        for k in inter:
            top[k] += 1
        if len(examples) < 3:
            examples.append((r.get("support"), sm))
for k, c in top.most_common(12):
    print("   %4d 次  %s" % (c, k[:90]))
for s, sm in examples:
    print("   例(support=%s): %s" % (s, sm[:130]))
