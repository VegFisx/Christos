# -*- coding: utf-8 -*-
r"""L1 收尾（2026-10-15）：5 个"病态分片"的分块重挖。

背景：这 5 片（876000/1242000/1362000/1512000/1668000）里各有一个会让 rdchiral
无限转的"病态分子"——每次重跑都卡在同一前缀，导致 900s 整片超时。
做法：每 500 行一块、每块 240 s 超时；正常块的结果追加进正式分片文件；
卡住的块跳过并**取证**（读该行 CXSMILES -> reports/ord_shards_full/_poison_rows.jsonl）。
可断点续跑（进度存 _stragglers_progress.json）。

需用 venv（duckdb/ord_schema）。用法: & $venv tools\extract_stragglers.py
"""
from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

STAGE = Path(r"D:\ProgramData\DSHNS\chemreact-staging")
OUT = STAGE / "reports" / "ord_shards_full"
PROGRESS = OUT / "_stragglers_progress.json"
POISON = OUT / "_poison_rows.jsonl"
BIG = STAGE / "ord-data" / "data" / "11" / \
    "ord_dataset-1158e351757f315b93cbcbe7bc55f38e.parquet"

SHARDS = [876000, 1242000, 1362000, 1512000, 1668000]   # 1740000 已完成（709s 整片成功）
CHUNK, TIMEOUT = 500, 240


def fetch_cx(off_abs: int):
    """读 parquet 第 off_abs 行的 CXSMILES（用于病态行取证）。"""
    try:
        import duckdb
        from ord_schema.proto import reaction_pb2
        con = duckdb.connect()
        row = con.execute(
            f"SELECT reaction FROM read_parquet('{BIG.as_posix()}') "
            f"OFFSET {off_abs} LIMIT 1").fetchone()
        if not row:
            return None
        rxn = reaction_pb2.Reaction()
        rxn.ParseFromString(row[0])
        return next((i.value for i in rxn.identifiers
                     if i.type == reaction_pb2.ReactionIdentifier.REACTION_CXSMILES
                     and i.value), None)
    except Exception:
        return None


def main() -> int:
    prog = json.loads(PROGRESS.read_text(encoding="utf-8")) if PROGRESS.exists() else {}
    for off in SHARDS:
        key = str(off)
        final = OUT / f"shard_{off:07d}.jsonl"
        st = prog.setdefault(key, {"done": [], "skipped": [], "started": False})
        if not st["started"]:
            final.write_text("", encoding="utf-8")
            st["started"] = True
            PROGRESS.write_text(json.dumps(prog, ensure_ascii=False, indent=1),
                                encoding="utf-8")
        done = set(st["done"])
        n_ok = n_skip = 0
        for ci in range(0, 6000, CHUNK):
            if ci in done:
                continue
            n = min(CHUNK, 6000 - ci)
            tmp = OUT / f"_chunk_{off:07d}_{ci:05d}.jsonl"
            t0 = time.time()
            try:
                subprocess.run(
                    [sys.executable, str(STAGE / "tools" / "retro_extract_shard.py"),
                     str(off + ci), str(n), str(tmp)],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                    timeout=TIMEOUT, check=False).returncode
                ok = True
            except subprocess.TimeoutExpired:
                ok = False
            if ok:
                if tmp.exists():
                    with open(tmp, encoding="utf-8") as f:
                        data = f.read()
                    tmp.unlink()
                    with open(final, "a", encoding="utf-8") as F:
                        F.write(data)
                st["done"].append(ci)
                n_ok += 1
                print("   o=%d chunk@%d OK（%.0fs）" % (off, ci, time.time() - t0), flush=True)
            else:
                st["skipped"].append({"chunk_start": off + ci, "n": n})
                n_skip += 1
                print("   o=%d chunk@%d 【病态块】超时 %ds，跳过并取证" % (off, ci, TIMEOUT),
                      flush=True)
                cx = fetch_cx(off + ci)
                with open(POISON, "a", encoding="utf-8") as f:
                    f.write(json.dumps({"shard": off, "chunk_start": off + ci,
                                        "n": n, "cxsmiles": cx},
                                       ensure_ascii=False) + "\n")
            PROGRESS.write_text(json.dumps(prog, ensure_ascii=False, indent=1),
                                encoding="utf-8")
        lines = sum(1 for _ in open(final, encoding="utf-8"))
        print("== 片 o=%d 收尾：行数 %d · 本次 OK %d 块 · 跳过 %d 块"
              % (off, lines, n_ok, n_skip), flush=True)
    print("全部 5 片处理完毕。进度文件：%s；病态行证据：%s" % (PROGRESS.name, POISON.name))
    return 0


if __name__ == "__main__":
    sys.exit(main())
