# -*- coding: utf-8 -*-
r"""验证 thermo 预算改成「按次数」后，结果不再依赖机器负载。

★ 怎么造"机器负载"这个变量？
  用 max_computations 模拟：
    · 同一批输入，用不同的【次数上限】跑 → 结果会不同（这是设计好的量限制）
    · 同一批输入，同样的次数上限，但用极小的【时间】紧急刹车跑
      → 老实现下结果会变；新实现下，只要次数没到，结果应当一致

  更直接的验证：把紧急刹车设成 0（模拟"机器很忙"），
  看结果与正常情况是否一致 —— 新实现应该一致（因为时间不再是主限制）。
"""
import sys
from pathlib import Path

STAGE = Path(r"D:\ProgramData\DSHNS\chemreact-staging")
sys.path.insert(0, r"D:\TCMAI\src")
sys.path.insert(0, str(STAGE / "api"))
for d in ("core", "conditions", "rules", "libs", "sources"):
    p = STAGE / d
    if p.is_dir():
        sys.path.insert(0, str(p))

from thermo import Thermo


class FakeMod:
    """假的 xTB 模块：不真算，直接给一个确定的数。"""
    CACHE_DIR = None

    def __init__(self):
        self.calls = 0

    def _inchikey(self, smiles):
        return "K" + str(abs(hash(smiles)) % 10**8)

    def get_g(self, smiles, n_conf=3, verbose=False):
        self.calls += 1
        return -100.0 - len(smiles) * 0.001


def make(budget_sec, max_computations):
    t = Thermo.__new__(Thermo)
    from pathlib import Path as P
    t.cache_dir = STAGE / "reports" / "_thermo_test_cache"
    t.cache_dir.mkdir(parents=True, exist_ok=True)
    for f in t.cache_dir.glob("*.json"):
        pass
    t.budget_sec = float(budget_sec)
    t.n_conf = 3
    t.max_computations = int(max_computations)
    from thermo import ThermoStats
    t.stats = ThermoStats()
    import time
    t._t0 = time.time()
    t._n_new = 0
    t._mod = FakeMod()
    t._ok = True
    return t


SMILES = [f"CC{'C' * i}O" for i in range(1, 30)]

print("=" * 88)
print("① 次数的限制是确定的（设计行为）")
print("=" * 88)
for cap in (5, 10, 20):
    t = make(3600, cap)
    got = sum(1 for s in SMILES if t.gibbs(s) is not None)
    print(f"  max_computations={cap:>3} → 算出了 {got} 个")

print()
print("=" * 88)
print("② ★ 关键：时间不再是主限制 → 把紧急刹车调到极小，结果应【不变】★")
print("=" * 88)
# 清缓存
cache = STAGE / "reports" / "_thermo_test_cache"
for f in cache.glob("*.json"):
    f.unlink()
t_normal = make(3600, 10)
n_normal = sum(1 for s in SMILES if t_normal.gibbs(s) is not None)

for f in cache.glob("*.json"):
    f.unlink()
t_busy = make(0.0, 10)          # 紧急刹车 = 0 秒，模拟"机器极忙"
n_busy = sum(1 for s in SMILES if t_busy.gibbs(s) is not None)

print(f"  正常（刹车 3600s，次数上限 10）: 算出 {n_normal} 个")
print(f"  ★忙★（刹车 0s，次数上限 10）  : 算出 {n_busy} 个")
if n_normal == n_busy:
    print("  ✓ 一致 —— 时间不再影响结果")
else:
    print("  ✗ 不一致 —— 时间仍然影响结果")
print(f"  （紧急刹车触发次数: {t_busy.stats.emergency_stop}）")

print()
print("=" * 88)
print("③ 旧行为对照：把次数上限设成极大，只靠时间限制")
print("=" * 88)
for f in cache.glob("*.json"):
    f.unlink()
t_old_style = make(0.0, 10**9)   # 次数无限，只有时间刹车
n_old = sum(1 for s in SMILES if t_old_style.gibbs(s) is not None)
print(f"  次数无限 + 刹车 0s → 算出 {n_old} 个（旧实现就是这个行为）")
print(f"  紧急刹车触发 {t_old_style.stats.emergency_stop} 次")
print("  → 这就是原来的问题：结果由墙钟时间决定")

for f in cache.glob("*.json"):
    f.unlink()
print("\n（测试缓存已清理）")
