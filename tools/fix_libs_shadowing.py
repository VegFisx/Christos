# -*- coding: utf-8 -*-
r"""
修复：libs 里的包【遮蔽】了 venv 里的包
==========================================

事故：
  venv 的 rdkit 2026.03.6，但 pip --target libs 又装了一个 2024.03.6 进去。
  libs 在 sys.path 前面 → 引擎实际加载的是【旧版】rdkit。

这是个严重错误：引擎的所有化学行为都可能因此改变。

修法：
  libs 只应【新增】venv 里没有的包；凡是 venv 里已有的，一律从 libs 删掉，
  让 Python 回落到 venv 的版本。
"""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

VENV_SP = Path(r"D:\TCMAI\venv\Lib\site-packages")
LIBS = Path(r"D:\ProgramData\DSHNS\chemreact-staging\libs")

DRY = "--apply" not in sys.argv


def top_level_names(root: Path):
    """目录里的一级包名（目录 + .py 文件 + .dist-info）。"""
    pkgs, dists = set(), set()
    if not root.is_dir():
        return pkgs, dists
    for p in root.iterdir():
        n = p.name
        if n.endswith(".dist-info") or n.endswith(".egg-info"):
            dists.add(n.split("-")[0].replace("_", "-").lower())
        elif n.endswith(".py") and not n.startswith("_"):
            pkgs.add(n[:-3])
        elif p.is_dir() and not n.startswith("_") and n != "__pycache__":
            if (p / "__init__.py").exists() or (p / "__init__.pyi").exists():
                pkgs.add(n)
            else:
                # 命名空间包 / 数据目录，也当作包名
                pkgs.add(n)
    return pkgs, dists


venv_pkgs, venv_dists = top_level_names(VENV_SP)
libs_pkgs, libs_dists = top_level_names(LIBS)

print("=" * 88)
print("① venv 里已有哪些包")
print("=" * 88)
print(f"  包目录 {len(venv_pkgs)} 个，dist-info {len(venv_dists)} 个")

print()
print("=" * 88)
print("② libs 里哪些【遮蔽】了 venv（同名）")
print("=" * 88)
overlap = sorted(libs_pkgs & venv_pkgs)
print(f"  同名包 {len(overlap)} 个：")
for n in overlap:
    print(f"      {n}")
# 另外：venv 里以 dist 形式存在、libs 里以包目录存在的也要看
print()
print("  libs 里同时存在的 dist-info（也一并删，避免 pip 认为已装）：")
overlap_d = sorted(libs_dists & venv_dists)
for n in overlap_d:
    print(f"      {n}")

# 关键包单独确认版本
print()
print("=" * 88)
print("③ 关键包版本对照")
print("=" * 88)
for name in ("rdkit", "numpy", "scipy", "pandas", "pyarrow", "Pillow",
             "pydantic", "requests", "urllib3", "certifi"):
    v = (VENV_SP / name / "__init__.py").exists()
    l = (LIBS / name / "__init__.py").exists()
    if v or l:
        print(f"  {name:<12} venv {'有' if v else '无':<4} libs {'有' if l else '无':<4}"
              f"{'  ★遮蔽★' if (v and l) else ''}")

print()
print("=" * 88)
print("④ 处置")
print("=" * 88)
targets = [LIBS / n for n in overlap if (LIBS / n).exists()]
targets += [p for p in LIBS.iterdir()
            if (p.name.endswith(".dist-info") or p.name.endswith(".egg-info"))
            and p.name.split("-")[0].replace("_", "-").lower() in venv_dists]
# 连同它们的 dist-info 一起（按包名匹配）
extra = []
for p in list(LIBS.iterdir()):
    if not (p.name.endswith(".dist-info") or p.name.endswith(".egg-info")):
        continue
    base = p.name.split("-")[0].replace("_", "-").lower()
    if base in {n.replace("_", "-").lower() for n in overlap}:
        extra.append(p)
targets = sorted(set(targets + extra))

if DRY:
    print(f"  【演练】将删除 {len(targets)} 项（加 --apply 才真删）:")
    for t in targets[:40]:
        print(f"      {t.name}")
    if len(targets) > 40:
        print(f"      …… 另有 {len(targets)-40} 项")
else:
    print(f"  正在删除 {len(targets)} 项…")
    ok = 0
    for t in targets:
        try:
            if t.is_dir():
                shutil.rmtree(t)
            else:
                t.unlink()
            ok += 1
        except Exception as e:
            print(f"      ✗ {t.name}: {e}")
    print(f"  已删除 {ok} 项")

print()
print("=" * 88)
print("⑤ 删除后 libs 里还剩什么（应全是 venv 没有的新包）")
print("=" * 88)
after_pkgs, after_dists = top_level_names(LIBS)
still = sorted(after_pkgs & venv_pkgs)
print(f"  剩余包目录 {len(after_pkgs)} 个，其中仍与 venv 同名的: {len(still)}")
for n in still[:20]:
    print(f"      ★ {n}")
if not still:
    print("      ✓ 没有遮蔽了")
