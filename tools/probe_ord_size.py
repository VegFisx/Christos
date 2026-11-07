# -*- coding: utf-8 -*-
r"""量 ORD 数据集体积 + 读 README（只打印摘要，不下载数据本体）。"""
import os
import sys
from pathlib import Path

os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")
sys.path.insert(0, r"D:\ProgramData\DSHNS\chemreact-staging\libs")

from huggingface_hub import HfApi, hf_hub_download  # noqa: E402

REPO = "Open-Reaction-Database/ord-data"
api = HfApi()

print("=" * 78)
print("① 仓库文件体积")
print("=" * 78)
tree = list(api.list_repo_tree(REPO, repo_type="dataset", recursive=True))
files = [t for t in tree if hasattr(t, "size") and t.size is not None]
total = sum(t.size for t in files)
print(f"  文件 {len(files)} 个，合计 {total/1024**3:.3f} GB ({total/1024**2:.1f} MB)")

by_dir = {}
for t in files:
    d = str(Path(t.path).parent)
    by_dir.setdefault(d, [0, 0])
    by_dir[d][0] += 1
    by_dir[d][1] += t.size
print("  按目录:")
for d, (n, s) in sorted(by_dir.items()):
    print(f"      {d:<24} {n:>4} 个  {s/1024**2:>10.1f} MB")

print("  最大的 5 个文件:")
for t in sorted(files, key=lambda x: -x.size)[:5]:
    print(f"      {t.size/1024**2:>9.1f} MB  {t.path}")

print()
print("=" * 78)
print("② README 摘要（前 40 行）")
print("=" * 78)
try:
    p = hf_hub_download(REPO, "README.md", repo_type="dataset")
    txt = Path(p).read_text(encoding="utf-8", errors="replace").splitlines()
    for line in txt[:40]:
        print("  " + line)
except Exception as ex:
    print(f"  ✗ {type(ex).__name__}: {str(ex)[:200]}")
