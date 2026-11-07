# -*- coding: utf-8 -*-
# 严格核对：用"映射号集合"判定是不是同一批原子原样穿过（映射号在一条反应内唯一）。
#   宽松同分子 + 映射号集合相同 = 真·原样穿过（产物和底物是同一个分子）
#   宽松同分子 + 映射号集合不同 = "同位占位"式误算（不同原子，只是片段长得一样）
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


def _maps(frag):
    return frozenset(int(x) for x in re.findall(r":(\d+)", frag))


def scan(name, items):
    loose = 0
    strict = 0
    strict_cases = []
    for tag, sm in items:
        if ">>" not in sm:
            continue
        l, r = sm.split(">>", 1)
        lf, rf = _split(l), _split(r)
        hit = False
        for a in lf:
            ka = _key(a)
            for b in rf:
                if ka == _key(b):
                    if not hit:
                        loose += 1
                    if _maps(a) == _maps(b) and _maps(a):
                        strict += 1
                        if len(strict_cases) < 4:
                            strict_cases.append((tag, a[:50], b[:50]))
                    hit = True
                    break
    print("%s：宽松 %d 条 -> 严格（映射号集合一致）%d 条" % (name, loose, strict))
    for tag, a, b in strict_cases:
        print("   行%s: %s  ==  %s" % (tag, a, b))


print()
print("== 挖矿 3 组分正向模板 ==")
items = []
for i, line in enumerate(open(r"reports\mined_forward_templates_3c.jsonl", encoding="utf-8")):
    line = line.strip()
    if line:
        r = json.loads(line)
        items.append((str(i), r.get("template") or r.get("smarts") or ""))
scan("mined_forward_templates_3c", items)

print()
print("== 逆模板 raw 文件 ==")
items = []
for i, line in enumerate(open(r"reports\retro_templates_clustered.jsonl", encoding="utf-8")):
    line = line.strip()
    if line:
        items.append((str(i), json.loads(line)["template"]))
scan("retro_templates_clustered", items)
