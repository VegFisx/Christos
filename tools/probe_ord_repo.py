# -*- coding: utf-8 -*-
r"""探查 ORD 数据集在 HuggingFace 镜像上的仓库结构（只打印形状，不下载内容）。

huggingface.co 被墙，走 hf-mirror.com。
"""
import os
import sys
from pathlib import Path

os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")
sys.path.insert(0, r"D:\ProgramData\DSHNS\chemreact-staging\libs")

from huggingface_hub import HfApi  # noqa: E402

api = HfApi()

CANDIDATES = [
    ("Open-Reaction-Database/ord-data", "dataset"),
    ("Open-Reaction-Database/ord-data", "model"),
    ("open-reaction-database/ord-data", "dataset"),
]

for repo_id, rtype in CANDIDATES:
    print("=" * 78)
    print(f"尝试 {repo_id}  (repo_type={rtype})")
    print("=" * 78)
    try:
        files = api.list_repo_files(repo_id, repo_type=rtype)
    except Exception as ex:
        print(f"  ✗ {type(ex).__name__}: {str(ex)[:200]}")
        continue

    print(f"  ✓ 文件总数 {len(files)}")
    # 只按后缀/前缀归类，不列全部
    from collections import Counter
    ext = Counter(Path(f).suffix or "(无后缀)" for f in files)
    print("  按后缀分布（前 12）:")
    for e, n in ext.most_common(12):
        print(f"      {e:<12} {n}")
    print("  前 15 个路径:")
    for f in files[:15]:
        print(f"      {f}")
    break
else:
    print("\n所有候选仓库都不可用。")
