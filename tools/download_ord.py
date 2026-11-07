# -*- coding: utf-8 -*-
r"""下载 ORD (Open Reaction Database) 全量数据到 D 盘。

背景：
  · huggingface.co 被墙，必须走 hf-mirror.com
  · 仓库 Open-Reaction-Database/ord-data，共 65 个文件 / 1.171 GB
  · 53 个 parquet 是反应数据本体，4 个 .pb 是原始 protobuf

落盘位置（全部在 D 盘，不占 C）：
  data  -> D:\ProgramData\DSHNS\chemreact-staging\ord-data
  cache -> D:\ProgramData\DSHNS\chemreact-staging\hf_cache

可重复执行：snapshot_download 会跳过已完整的文件。
"""
import os
import sys
import time
from pathlib import Path

STAGE = Path(r"D:\ProgramData\DSHNS\chemreact-staging")
ORD_DIR = STAGE / "ord-data"
HF_CACHE = STAGE / "hf_cache"

os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"
os.environ["HF_HOME"] = str(HF_CACHE)
sys.path.insert(0, str(STAGE / "libs"))

from huggingface_hub import snapshot_download  # noqa: E402

REPO = "Open-Reaction-Database/ord-data"

ORD_DIR.mkdir(parents=True, exist_ok=True)
HF_CACHE.mkdir(parents=True, exist_ok=True)

print("=" * 78)
print("下载 ORD 数据（走 hf-mirror.com）")
print("=" * 78)
print(f"  仓库   : {REPO}")
print(f"  落盘   : {ORD_DIR}")
print(f"  缓存   : {HF_CACHE}")
print(f"  endpoint: {os.environ['HF_ENDPOINT']}")
print()

t0 = time.time()
try:
    path = snapshot_download(
        repo_id=REPO,
        repo_type="dataset",
        local_dir=str(ORD_DIR),
        max_workers=4,
    )
except Exception as ex:
    print(f"✗ 下载失败 {type(ex).__name__}: {ex}")
    sys.exit(1)

dt = time.time() - t0
print(f"\n✓ 下载完成，耗时 {dt/60:.1f} 分钟")
print(f"  返回路径: {path}")

# 核对落盘结果
n = 0
total = 0
for p in ORD_DIR.rglob("*"):
    if p.is_file():
        n += 1
        total += p.stat().st_size
print(f"  实际文件 {n} 个，合计 {total/1024**3:.3f} GB")
print(f"  期望文件 65 个，合计 1.171 GB")
print(f"  一致: {'✓' if n == 65 else '✗ 文件数不符'}")
