# -*- coding: utf-8 -*-
r"""抽模板的【单片 worker】：只负责把一片 ORD 反应抽成模板，写 JSONL。

用法: python retro_extract_shard.py <offset> <n> <out.jsonl>
设计成独立进程，是为了避开"进程池/线程池会被个别分子整池挂死"这个坑（实测两次）。
"""
import json
import os
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
    sys.path.insert(0, str(_p))

BIG = STAGE / "ord-data" / "data" / "11" / \
    "ord_dataset-1158e351757f315b93cbcbe7bc55f38e.parquet"


def main():
    off, n, out_path = int(sys.argv[1]), int(sys.argv[2]), sys.argv[3]
    # 堵住 rdchiral 在失败路径上的 print（必须在 import 之后、开始之前）
    _sink = open(os.devnull, "w")
    _old = os.dup(1)

    import duckdb
    from rdkit import Chem, RDLogger
    RDLogger.DisableLog("rdApp.*")
    import rdchiral.template_extractor as te
    from rdchiral.template_extractor import extract_from_reaction
    from ord_schema.proto import reaction_pb2

    te.VERBOSE = False
    con = duckdb.connect()
    con.execute("SET memory_limit='1200MB'")
    con.execute("SET threads=1")
    rows = con.execute(
        f"SELECT reaction FROM read_parquet('{BIG.as_posix()}') OFFSET {off} LIMIT {n}"
    ).fetchall()

    stat = Counter()
    done = 0
    with open(out_path, "w", encoding="utf-8") as f:
        for (blob,) in rows:
            done += 1
            rxn = reaction_pb2.Reaction()
            try:
                rxn.ParseFromString(blob)
            except Exception:
                stat["protobuf失败"] += 1
                continue
            cx = next((i.value for i in rxn.identifiers
                       if i.type == reaction_pb2.ReactionIdentifier.REACTION_CXSMILES
                       and i.value), None)
            if not cx:
                stat["无CXSMILES"] += 1
                continue
            body = cx.split("|", 1)[0] if "|" in cx else cx
            parts = body.split(">")
            if len(parts) == 2:
                lhs, rhs = parts
            elif len(parts) == 3:
                lhs, _m, rhs = parts
            else:
                stat["段数异常"] += 1
                continue
            rs = [p for p in lhs.split(".") if p.strip()]
            ps = [p for p in rhs.split(".") if p.strip()]
            if not rs or not ps:
                stat["空侧"] += 1
                continue
            if not any(":" in p for p in ps):
                stat["产物无映射"] += 1
                continue
            # ★ rdchiral 要 reactants / products（复数）；传单数会 KeyError（上次就死在这）
            os.dup2(_sink.fileno(), 1)
            try:
                t = extract_from_reaction({"reactants": ".".join(rs),
                                           "products": ".".join(ps), "_id": "x"})
            except Exception as e:
                t = None
                stat[f"异常:{type(e).__name__}"] += 1
            finally:
                sys.stdout.flush()
                os.dup2(_old, 1)
            if not t or not t.get("reaction_smarts"):
                stat["rdchiral拒绝"] += 1
                continue
            tpl = t["reaction_smarts"]
            if ">>" not in tpl:
                stat["无SMARTS"] += 1
                continue
            f.write(json.dumps({"template": tpl,
                                "rx": ".".join(rs) + ">>" + ".".join(ps)},
                               ensure_ascii=False) + "\n")
            stat["成功"] += 1
    print(json.dumps({"offset": off, "n": n, "done": done, "stat": dict(stat)},
                     ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
