# -*- coding: utf-8 -*-
r"""E-1 并行总控：把 ORD 分片，交给独立进程跑，再合并成覆盖率表。

为什么不用进程池/线程池：本工作区实测两次"个别分子让 RDKit/rdchiral 死循环、整池挂死"。
所以用独立子进程 + 每片超时，一片挂了只损失一片，且会被计数（不静默）。

用法:
  python run_aux_reagent_coverage.py                       # 全量 1,771,032 条，8 进程，每片 5 万
  python run_aux_reagent_coverage.py --total 200000 --workers 8
  python run_aux_reagent_coverage.py --shard-size 20000 --workers 10
"""
import argparse
import json
import subprocess
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

STAGE = Path(r"D:\ProgramData\DSHNS\chemreact-staging")
sys.path.insert(0, str(STAGE / "tools"))
sys.path.insert(0, str(STAGE / "libs"))

from extract_aux_reagent_coverage import (BIG, OUT, summarize,  # noqa: E402
                                          REQUIRED_COV, OPTIONAL_COV)

SHARD_DIR = STAGE / "reports" / "_aux_shards"
WORKER = STAGE / "tools" / "extract_aux_reagent_coverage.py"


def parquet_rows():
    import duckdb
    con = duckdb.connect()
    con.execute("SET memory_limit='800MB'")
    n = con.execute(f"SELECT count(*) FROM read_parquet('{BIG.as_posix()}')").fetchone()[0]
    con.close()
    return int(n)


def merge_shards():
    """把 reports/_aux_shards/*.json 合并成 (total, aux_hits, stat, n_done, n_classified)。
    同一 (offset, n) 只算一次（取 n_done 最大的那份），避免重跑/重试时重复计数。"""
    total = Counter()
    aux_hits = defaultdict(Counter)
    stat = Counter()
    n_done = n_classified = 0
    best = {}
    files = sorted(SHARD_DIR.glob("shard_*.json"))
    for p in files:
        d = json.loads(p.read_text(encoding="utf-8"))
        key = (d.get("offset"), d.get("n"))
        if key in best and best[key]["n_done"] >= d["n_done"]:
            continue
        best[key] = d
    for key in sorted(best, key=lambda k: (k[0] if k[0] is not None else -1)):
        d = best[key]
        n_done += d["n_done"]
        n_classified += d["n_classified"]
        for k, v in d["total"].items():
            total[k] += v
        for k, v in d["aux_hits"].items():
            for smi, c in v.items():
                aux_hits[k][smi] += c
        for k, v in d["stat"].items():
            stat[k] += v
    return total, aux_hits, stat, n_done, n_classified, len(files), len(best)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--total", type=int, default=None, help="最多统计多少条（默认全量）")
    ap.add_argument("--shard-size", type=int, default=50000)
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--timeout", type=int, default=3600, help="每片超时秒数")
    ap.add_argument("--out", default=str(OUT))
    ap.add_argument("--merge-only", action="store_true",
                    help="不跑新分片，只合并 reports/_aux_shards/ 里已有的")
    args = ap.parse_args()

    t_all = time.time()
    SHARD_DIR.mkdir(parents=True, exist_ok=True)

    if not args.merge_only:
        total_rows = args.total if args.total else parquet_rows()
        ranges = [(o, min(args.shard_size, total_rows - o))
                  for o in range(0, total_rows, args.shard_size)]
        ranges = [(o, n) for o, n in ranges if n > 0]
        print("=" * 96)
        print(f"E-1 并行覆盖率统计：{total_rows:,} 条 / {len(ranges)} 片 / {args.workers} 进程")
        print("=" * 96, flush=True)

        pending = []
        skipped = 0
        for off, n in ranges:
            if (SHARD_DIR / f"shard_{off}_{n}.json").exists():
                skipped += 1
                continue
            pending.append((off, n))
        print(f"  可续跑：跳过已存在的分片 {skipped} 个，待跑 {len(pending)} 个", flush=True)
        running = []          # (proc, off, n, out_path, t0)
        done = []             # (off, n, out_path, tag)
        failed = []           # (off, n, reason)

        def start(off, n, tag=""):
            p = SHARD_DIR / f"shard_{off}_{n}{tag}.json"
            proc = subprocess.Popen(
                [sys.executable, str(WORKER), "--shard", str(off), str(n), str(p)],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                encoding="utf-8", errors="replace")
            running.append((proc, off, n, p, time.time()))

        while pending or running:
            while pending and len(running) < args.workers:
                off, n = pending.pop(0)
                start(off, n)
            time.sleep(2)
            for item in list(running):
                proc, off, n, p, t0 = item
                if proc.poll() is None:
                    if time.time() - t0 > args.timeout:
                        proc.kill()
                        proc.communicate()
                        running.remove(item)
                        failed.append((off, n, f"超时 {args.timeout}s 已杀"))
                        print(f"  [片 {off:,}+{n:,}] 超时被杀", flush=True)
                    continue
                out, err = proc.communicate()
                running.remove(item)
                if proc.returncode != 0:
                    failed.append((off, n, f"退出码 {proc.returncode}: {err.strip()[-200:]}"))
                    print(f"  [片 {off:,}+{n:,}] 失败 rc={proc.returncode}", flush=True)
                else:
                    done.append((off, n, p, ""))
                    print(f"  [片 {off:,}+{n:,}] 完成 {out.strip()[:150]}", flush=True)
        for off, n, why in failed:
            print(f"  !! 失败片 {off:,}+{n:,}: {why}")

    total, aux_hits, stat, n_done, n_classified, n_files, n_uniq = merge_shards()
    print()
    print("=" * 96)
    print(f"合并：{n_uniq} 个分片（文件 {n_files} 个）；"
          f"处理 {n_done:,} 条，归类成功 {n_classified:,} 条（{len(total)} 类）")
    print("=" * 96)
    print("  失败/跳过原因（计数）：")
    for k, v in stat.most_common(14):
        print(f"    {k:<26} {v:,}")
    print(f"  实际覆盖率口径的分母 = 归类成功的 {n_classified:,} 条"
          f"（不是扫描的 {n_done:,} 条）")

    result = summarize(total, aux_hits, out_path=Path(args.out))
    print(f"  总耗时 {time.time()-t_all:.0f}s")
    print(f"  分片原始件留在 {SHARD_DIR.name}/（可复核）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
