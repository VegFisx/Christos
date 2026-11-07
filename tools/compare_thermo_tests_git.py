# -*- coding: utf-8 -*-
r"""用 git 判断：thermo 的三个测试失败，是我改出来的，还是本来就有的？"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

STAGE = Path(r"D:\ProgramData\DSHNS\chemreact-staging")
sys.path.insert(0, str(STAGE / "libs"))
from dulwich.repo import Repo

PY = r"D:\TCMAI\venv\Scripts\python.exe"
TESTS = ["test_thermo", "test_thermo_final", "test_thermo_integration"]

repo = Repo(str(STAGE))
target = None
for entry in repo.get_walker():
    m = entry.commit.message.decode("utf-8", "replace")
    if m.startswith("ROUND26:"):
        target = entry.commit
        break
if target is None:
    print("找不到 ROUND26 提交")
    raise SystemExit(1)
print(f"基线提交 {target.id.decode()[:12]}: {target.message.decode('utf-8').splitlines()[0]}")

tree = repo[target.tree]
core = repo[tree[b"core"][1]]
old_thermo = repo[core[b"thermo.py"][1]].data.decode("utf-8")
cur_thermo = (STAGE / "core" / "thermo.py").read_text(encoding="utf-8")
print(f"旧 thermo.py {len(old_thermo)} 字节 / 当前 {len(cur_thermo)} 字节")


def run_tests(label):
    out = {}
    for t in TESTS:
        f = STAGE / "tools" / f"{t}.py"
        if not f.exists():
            continue
        r = subprocess.run([PY, "-X", "utf8", str(f)],
                           capture_output=True, text=True,
                           encoding="utf-8", errors="replace")
        line = ""
        for ln in r.stdout.splitlines():
            if ln.strip().startswith("结果："):
                line = ln.strip()
        out[t] = line or "(无结果行)"
    print(f"\n  【{label}】")
    for k, v in out.items():
        print(f"    {k:<26} {v}")
    return out


print()
print("=" * 88)
print("对照：同一批测试，分别用旧/新 thermo.py 跑")
print("=" * 88)

(STAGE / "core" / "thermo.py").write_text(old_thermo, encoding="utf-8")
old_res = run_tests("旧 thermo.py（我改之前）")

(STAGE / "core" / "thermo.py").write_text(cur_thermo, encoding="utf-8")
new_res = run_tests("新 thermo.py（当前）")

print()
print("=" * 88)
print("判定")
print("=" * 88)
for t in TESTS:
    o, n = old_res.get(t, ""), new_res.get(t, "")
    if o == n:
        print(f"  {t:<26} 旧=新  → {'本来就这样（非我引入）' if '失败' in o and '0 失败' not in o else '一致通过'}")
    else:
        print(f"  {t:<26} ★变了★  旧: {o}   新: {n}")
