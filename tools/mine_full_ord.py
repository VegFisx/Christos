# -*- coding: utf-8 -*-
r"""L1（2026-10-14）：全量 ORD 挖矿 runner —— 把 uspto-grants parquet 的第 60,000 行到
1,771,032 行按 6,000/片并行抽取（前 60,000 行已由既有分片覆盖，不重复挖）。

* 可断点续跑：已有输出的片自动跳过
* 每片一个独立子进程（沿用 retro_extract_shard.py 的设计，避免整池被个别分子挂死）
* 输出：reports/ord_shards_full/shard_<offset:07d>.jsonl（+ 同名 .log）
* 需要 Python 3.12（duckdb/ord_schema 在 libs）：用 venv 跑

用法: & $venv tools\mine_full_ord.py [workers=6]
"""
from __future__ import annotations

import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

STAGE = Path(r"D:\ProgramData\DSHNS\chemreact-staging")
OUT = STAGE / "reports" / "ord_shards_full"
STEP = 6000
TOTAL = 1771032
START = 60000


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    workers = int(sys.argv[1]) if len(sys.argv) > 1 else 6
    offsets = list(range(START, TOTAL, STEP))
    todo = [o for o in offsets if not (OUT / f"shard_{o:07d}.jsonl").exists()]
    print("L1 挖矿：总片 %d · 已完成 %d · 本次待挖 %d · 并发 %d · 输出 %s"
          % (len(offsets), len(offsets) - len(todo), len(todo), workers, OUT), flush=True)

    t0 = time.time()
    done = 0

    def run(o: int):
        out = OUT / f"shard_{o:07d}.jsonl"
        log = OUT / f"shard_{o:07d}.log"
        t1 = time.time()
        with open(log, "w", encoding="utf-8") as lg:
            rc = subprocess.run(
                [sys.executable, str(STAGE / "tools" / "retro_extract_shard.py"),
                 str(o), str(STEP), str(out)],
                stdout=lg, stderr=lg).returncode
        return o, rc, time.time() - t1

    bad = 0
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futs = [ex.submit(run, o) for o in todo]
        for f in as_completed(futs):
            o, rc, dt = f.result()
            done += 1
            if rc != 0:
                bad += 1
                print("   [warn] 片 o=%d 退出码 %d（%.0fs）" % (o, rc, dt), flush=True)
            if done % 10 == 0:
                print("   ... %d/%d 片（%.0fs；失败 %d）"
                      % (done, len(todo), time.time() - t0, bad), flush=True)

    files = sorted(OUT.glob("shard_*.jsonl"))
    n_rec = 0
    for p in files:
        with open(p, encoding="utf-8") as f:
            n_rec += sum(1 for _ in f)
    print("完成：片 %d · 抽取记录 %d · 失败片 %d · 耗时 %.0fs"
          % (len(files), n_rec, bad, time.time() - t0), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
