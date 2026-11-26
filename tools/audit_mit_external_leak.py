# -*- coding: utf-8 -*-
"""审计「MIT 外部模板」的命中是否只是近似重复。

重建 MIT 外部样本（与 miner 同一抽样/排除口径），检查：
  · MIT-only shard0 的命中，在 MIT 外部样本里是否同主产物/同底物/完全相同；
  · merged 相对 train+stereo 新增的命中，是否同样。
"""
import csv
import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(r"D:\ProgramData\DSHNS\chemreact-staging")
for p in (ROOT / "libs",):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from rdkit import Chem, RDLogger  # noqa: E402

RDLogger.DisableLog("rdApp.*")

MIT = ROOT / "reports" / "paper" / "data" / "uspto_mit" / "USPTO_MIT.csv"
FIFTY = ROOT / "reports" / "paper" / "data" / "uspto50k_mapped.jsonl"
TEST = ROOT / "reports" / "paper" / "data" / "uspto50k_official" / "raw_test.csv"
RES = ROOT / "reports" / "paper" / "results"
_MAP = re.compile(r"\[([^:\]]*):\d+\]")
SEED = "20261121"
PCT = 2.1


def strip_map(s):
    return _MAP.sub(r"[\1]", s or "")


def canon(s, iso=True):
    m = Chem.MolFromSmiles(s) if s else None
    return Chem.MolToSmiles(m, isomericSmiles=iso) if m is not None else ""


def split3(rxn):
    p = (rxn or "").split(">")
    if len(p) == 3:
        return p[0], p[2]
    if len(p) == 2:
        return p[0], p[1]
    return "", ""


def sig(rxn):
    left, right = split3(rxn)
    rs = frozenset(c for c in (canon(strip_map(x)) for x in left.split(".")) if c)
    ps = frozenset(c for c in (canon(strip_map(x)) for x in right.split(".")) if c)
    return rs, ps


def main_part(right, iso=True):
    ps = [canon(strip_map(x), iso) for x in right.split(".") if strip_map(x)]
    ps = [x for x in ps if x]
    if not ps:
        return ""
    return max(ps, key=lambda s: len(s))


def load_50k():
    out = set()
    for line in open(FIFTY, encoding="utf-8"):
        out.add(sig(json.loads(line).get("mapped_rxn") or ""))
    return out


def load_hits(tag):
    d = {}
    for line in open(RES / ("forward_official_test__%s.jsonl" % tag), encoding="utf-8"):
        x = json.loads(line)
        d[x["i"]] = bool(x.get("hit"))
    return d


def main():
    print("重建 MIT 外部样本 ...", flush=True)
    ex = load_50k()
    ext = set()
    with open(MIT, encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            rxn = row.get("reactions") or ""
            h = hashlib.md5((SEED + rxn).encode("utf-8")).hexdigest()
            if (int(h[:8], 16) % 10000) >= PCT * 100:
                continue
            if sig(rxn) in ex:
                continue
            ext.add(sig(rxn))
    ext_main = set()
    ext_exact = set()
    for rs, ps in ext:
        main = max(ps, key=len) if ps else ""
        ext_main.add(main)
        ext_exact.add((rs, main))
    ext_react = {rs for rs, _ps in ext}
    print("MIT 外部唯一 signature %d" % len(ext))

    # test rows
    rows = {}
    with open(TEST, encoding="utf-8", newline="") as f:
        for i, row in enumerate(csv.DictReader(f)):
            left, right = split3(row["reactants>reagents>production"])
            rs = [strip_map(x) for x in left.split(".") if x.strip()]
            if not (1 <= len(rs) <= 2) or not right.strip():
                continue
            rows[i] = (frozenset(canon(x) for x in rs if canon(x)),
                       main_part(right, iso=False))

    def audit(name, ids):
        a = b = c = 0
        for i in ids:
            rec = rows.get(i)
            if not rec:
                continue
            rs, main = rec
            if main and main in ext_main:
                a += 1
            if rs in ext_react:
                b += 1
            if (rs, main) in ext_exact:
                c += 1
        n = len(ids)
        print("%-18s n=%-4d same_main %d (%.1f%%) · same_react %d (%.1f%%)"
              " · exact_flat %d (%.1f%%)"
              % (name, n, a, 100.0 * a / max(1, n), b, 100.0 * b / max(1, n),
                 c, 100.0 * c / max(1, n)))

    mit = load_hits("mit_only_s0")
    train = load_hits("full5_tr1_stf_s0")
    merged = load_hits("merged_s0")
    audit("MIT-only 命中", {i for i, h in mit.items() if h})
    new = {i for i in merged if merged[i] and not train.get(i)}
    audit("merged 新增命中", new)
    print("merged 新增命中明细：", sorted(new)[:20])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
