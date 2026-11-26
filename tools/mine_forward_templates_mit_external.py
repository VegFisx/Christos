# -*- coding: utf-8 -*-
"""从 USPTO-MIT 的**外部**反应挖正向模板（排除整个 USPTO-50k）。

协议（写死）：
  1. 50k 排除集 = uspto50k_mapped.jsonl 的全部 signature（规范化底物集合 + 全产物集合）；
     MIT 中 signature 命中的反应一律不参与（不是只排除 test）。
  2. MIT 先按 md5(seed+reaction) 抽样（默认 2.1%，约 1 万条），再做 signature 检查；
     这样只对样本做 RDKit 规范化。
  3. 样本反应去掉 reagents（只保留 reactants>>products），用本地 RXNMapper 映射，
     RDChiral 抽 retro 模板并翻成 forward；support = 相同 forward SMARTS 的条数。
  4. 输出 reports/mined_forward_templates_mit_external.jsonl + meta json。

用法：
  python -I tools\\mine_forward_templates_mit_external.py --pct 2.1
"""
from __future__ import annotations

import argparse
import collections
import csv
import hashlib
import json
import re
import sys
import time
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

ROOT = Path(__file__).resolve().parents[1]
for _p in (ROOT / "libs", ROOT / "tools", ROOT / "core"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from rdkit import Chem, RDLogger  # noqa: E402
from rdchiral.template_extractor import extract_from_reaction  # noqa: E402
from rxnmapper import RXNMapper  # noqa: E402

RDLogger.DisableLog("rdApp.*")

MIT = ROOT / "reports" / "paper" / "data" / "uspto_mit" / "USPTO_MIT.csv"
FIFTY = ROOT / "reports" / "paper" / "data" / "uspto50k_mapped.jsonl"
OUT = ROOT / "reports" / "mined_forward_templates_mit_external.jsonl"
META = ROOT / "reports" / "mined_forward_templates_mit_external.meta.json"

_MAP = re.compile(r"\[([^:\]]*):\d+\]")


def strip_map(s):
    return _MAP.sub(r"[\1]", s or "")


def canon(s):
    m = Chem.MolFromSmiles(s) if s else None
    return Chem.MolToSmiles(m) if m is not None else ""


def split3(rxn):
    p = (rxn or "").split(">")
    if len(p) == 3:
        return p[0], p[1], p[2]
    if len(p) == 2:
        return p[0], "", p[1]
    return "", "", ""


def sig(rxn):
    left, _mid, right = split3(rxn)
    rs = frozenset(c for c in (canon(strip_map(x)) for x in left.split(".")) if c)
    ps = frozenset(c for c in (canon(strip_map(x)) for x in right.split(".")) if c)
    return (rs, ps)


def load_50k_sigs():
    out = set()
    with open(FIFTY, encoding="utf-8") as f:
        for line in f:
            d = json.loads(line)
            out.add(sig(d.get("mapped_rxn") or ""))
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pct", type=float, default=2.1, help="MIT 抽样百分比")
    ap.add_argument("--seed", default="20261121")
    ap.add_argument("--batch", type=int, default=64)
    a = ap.parse_args()
    t0 = time.time()

    print("读 50k 排除集 ...", flush=True)
    ex = load_50k_sigs()
    print("  50k 唯一 signature %d（%.0fs）" % (len(ex), time.time() - t0), flush=True)

    # 1) 哈希抽样 + 排除 50k
    sample = []
    n_rows = n_hash = n_excl = n_bad = 0
    with open(MIT, encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            n_rows += 1
            rxn = row.get("reactions") or ""
            h = hashlib.md5((a.seed + rxn).encode("utf-8")).hexdigest()
            if (int(h[:8], 16) % 10000) >= a.pct * 100:
                continue
            n_hash += 1
            left, _mid, right = split3(rxn)
            if not left.strip() or not right.strip():
                n_bad += 1
                continue
            if sig(rxn) in ex:
                n_excl += 1
                continue
            sample.append(left + ">>" + right)
    print("MIT %d 行 · 抽样 %d · 坏 %d · 50k重合排除 %d · 外部样本 %d（%.0fs）"
          % (n_rows, n_hash, n_bad, n_excl, len(sample), time.time() - t0), flush=True)

    # 2) RXNMapper 映射
    mapper = RXNMapper()
    mapped = []
    n_map_fail = 0
    t1 = time.time()
    for k in range(0, len(sample), a.batch):
        batch = sample[k:k + a.batch]
        try:
            outs = mapper.get_attention_guided_atom_maps(batch)
        except Exception as ex_:
            print("  [warn] 映射批次失败：%s: %s" % (type(ex_).__name__, ex_), flush=True)
            n_map_fail += len(batch)
            continue
        for src, o in zip(batch, outs):
            mr = (o or {}).get("mapped_rxn") or ""
            if ">>" not in mr:
                n_map_fail += 1
                continue
            mapped.append(mr)
        if (k // a.batch + 1) % 20 == 0:
            print("  ...映射 %d/%d  %.0fs" % (len(mapped), len(sample),
                                             time.time() - t1), flush=True)
    print("映射成功 %d，失败 %d（%.0fs）" % (len(mapped), n_map_fail,
                                             time.time() - t1), flush=True)

    # 3) RDChiral 抽模板
    cnt = collections.Counter()
    n_extract_fail = 0
    for mr in mapped:
        left, right = mr.split(">>", 1)
        try:
            res = extract_from_reaction({"reactants": left, "products": right,
                                         "agents": "", "_id": "x"})
            tpl = (res or {}).get("reaction_smarts") or ""
        except Exception:
            tpl = ""
        if ">>" not in tpl:
            n_extract_fail += 1
            continue
        a_, b_ = tpl.split(">>", 1)
        cnt[b_ + ">>" + a_] += 1

    with open(OUT, "w", encoding="utf-8") as f:
        for t, n in cnt.most_common():
            f.write(json.dumps({"template": t, "support": n,
                                "src": "uspto_mit_external"}, ensure_ascii=False) + "\n")
    meta = {
        "protocol": "MIT md5 sample; exclude all uspto50k signatures; drop reagents; "
                    "RXNMapper; RDChiral forward flip",
        "seed": a.seed, "pct": a.pct,
        "mit_rows": n_rows, "sampled": n_hash, "bad": n_bad,
        "excluded_50k": n_excl, "external_sample": len(sample),
        "mapped": len(mapped), "map_fail": n_map_fail,
        "extract_fail": n_extract_fail, "unique_templates": len(cnt),
        "support_ge2": sum(1 for _, n in cnt.items() if n >= 2),
        "seconds": round(time.time() - t0, 1),
    }
    META.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    print("完成：唯一模板 %d（support>=2: %d）· 抽取失败 %d · %.0fs"
          % (len(cnt), meta["support_ge2"], n_extract_fail, time.time() - t0))
    print("输出 ->", OUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
