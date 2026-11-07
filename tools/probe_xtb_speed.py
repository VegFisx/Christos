# -*- coding: utf-8 -*-
"""摸底：xTB 到底多慢？能算多少个分子？

同时验证：把缓存目录重定向到暂存区后，不会往 D:\TCMAI 里写东西。
"""
import sys
import time
from pathlib import Path

TCMAI_SRC = Path(r"D:\TCMAI\src")
STAGE = Path(r"D:\ProgramData\DSHNS\chemreact-staging")
sys.path.insert(0, str(TCMAI_SRC))

import thermo_xtb  # noqa: E402

# ★ 关键：立刻把缓存目录改到暂存区，绝不往用户项目里写
SAFE_CACHE = STAGE / "xtb_cache"
SAFE_CACHE.mkdir(parents=True, exist_ok=True)
thermo_xtb.CACHE_DIR = SAFE_CACHE

print(f"xtb.exe       : {thermo_xtb.XTB}")
print(f"存在          : {thermo_xtb.XTB.exists()}")
print(f"原缓存目录    : D:\\TCMAI\\data\\xtb_cache")
print(f"已重定向到    : {thermo_xtb.CACHE_DIR}")
print(f"暂存区缓存数  : {len(list(SAFE_CACHE.glob('*.json')))}")
print()

TESTS = [
    ("水", "O", 3),
    ("甲醇", "CO", 6),
    ("乙酸", "CC(=O)O", 8),
    ("苯甲酸", "OC(=O)c1ccccc1", 15),
    ("葡萄糖", "OC[C@H]1OC(O)[C@H](O)[C@@H](O)[C@@H]1O", 23),
    ("苯甲酸甲酯", "COC(=O)c1ccccc1", 16),
]

print(f"{'分子':<12}{'原子数':>6}{'耗时(s)':>10}   G (Hartree)")
print("-" * 60)
times = []
for name, smi, _n in TESTS:
    t0 = time.time()
    g = thermo_xtb.get_g(smi, n_conf=3, verbose=False)
    dt = time.time() - t0
    times.append((name, dt, g))
    status = f"{g:.6f}" if g is not None else "★失败★"
    print(f"{name:<12}{'':>6}{dt:>10.1f}   {status}")

print()
print("=" * 70)
print("结论")
print("=" * 70)
ok = [t for t in times if t[2] is not None]
if ok:
    avg = sum(t[1] for t in ok) / len(ok)
    print(f"成功 {len(ok)}/{len(TESTS)}，平均 {avg:.1f} 秒/分子")
    print(f"→ 100 个分子约需 {avg*100/60:.0f} 分钟")
    print(f"→ 350 个分子约需 {avg*350/60:.0f} 分钟")
else:
    print("全部失败，xTB 可能跑不起来")

print()
print("=== 确认没有写进 D:\\TCMAI\\data\\xtb_cache ===")
user_cache = Path(r"D:\TCMAI\data\xtb_cache")
files = list(user_cache.glob("*.json")) if user_cache.exists() else []
print(f"用户目录缓存文件数: {len(files)}（应仍为 7，未增加）")
print(f"暂存区缓存文件数  : {len(list(SAFE_CACHE.glob('*.json')))}")
