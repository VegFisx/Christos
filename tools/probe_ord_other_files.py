# -*- coding: utf-8 -*-
r"""一次性探针：另外 52 个 parquet 里有没有 reaction / CXSMILES（决定是否纳入砌块口径）。"""
import sys
from pathlib import Path
for _s in (sys.stdout, sys.stderr):
    try: _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception: pass
STAGE = Path(r"D:\ProgramData\DSHNS\chemreact-staging")
sys.path.insert(0, str(STAGE / "libs"))
import duckdb
from ord_schema.proto import reaction_pb2

pq = sorted((STAGE / "ord-data" / "data").rglob("*.parquet"))
con = duckdb.connect(); con.execute("SET memory_limit='1500MB'"); con.execute("SET threads=2")
print(f"共 {len(pq)} 个 parquet")
for p in pq:
    n = con.execute(f"SELECT num_rows FROM parquet_file_metadata('{p.as_posix()}')").fetchone()[0]
    cols = [d[0] for d in con.execute(f"DESCRIBE SELECT * FROM read_parquet('{p.as_posix()}')").fetchall()]
    has_rxn = "reaction" in cols
    n_cx = 0
    if has_rxn and n:
        rows = con.execute(f"SELECT reaction FROM read_parquet('{p.as_posix()}') LIMIT 200").fetchall()
        for (b,) in rows:
            r = reaction_pb2.Reaction()
            try: r.ParseFromString(b)
            except Exception: continue
            if any(i.type == reaction_pb2.ReactionIdentifier.REACTION_CXSMILES and i.value
                   for i in r.identifiers):
                n_cx += 1
    print(f"  {n:>9,} 行  列={cols}  有reaction={has_rxn}  前200条有CX={n_cx}  {p.name[:50]}")
