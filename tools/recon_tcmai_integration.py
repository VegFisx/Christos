# -*- coding: utf-8 -*-
r"""一次性侦察：TCMAI 怎么跑、怎么打包、逆合成能不能挂进去。只打印摘要。"""
import re
import sys
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

T = Path(r"D:\TCMAI")

print("=" * 78)
print("① launcher.py —— 导入与 UI 框架")
print("=" * 78)
txt = (T / "launcher.py").read_text(encoding="utf-8", errors="replace")
for line in txt.splitlines():
    s = line.strip()
    if re.match(r"^(import|from)\s", s):
        print("   " + s[:110])
print("   --- 关键词命中 ---")
for kw in ("tkinter", "PyQt", "PySide", "flask", "fastapi", "uvicorn", "webview",
           "threading", "subprocess", "QMainWindow", "Tk("):
    n = len(re.findall(re.escape(kw), txt))
    if n:
        print(f"   {kw:<12} {n} 次")
print(f"   总行数 {len(txt.splitlines())}")

print()
print("=" * 78)
print("② TCMAI.spec —— 打包配置")
print("=" * 78)
print((T / "TCMAI.spec").read_text(encoding="utf-8", errors="replace")[:900])

print()
print("=" * 78)
print("③ requirements.txt 关键包")
print("=" * 78)
req = (T / "requirements.txt").read_text(encoding="utf-8", errors="replace")
for line in req.splitlines():
    if any(k in line.lower() for k in ("rdkit", "torch", "xtb", "numpy", "flask",
                                        "fastapi", "pyqt", "streamlit", "openai")):
        print("   " + line[:100])

print()
print("=" * 78)
print("④ retrofit：chemreact-staging\api 的接口形状")
print("=" * 78)
A = Path(r"D:\ProgramData\DSHNS\chemreact-staging\api")
for p in sorted(A.glob("*.py")):
    t = p.read_text(encoding="utf-8", errors="replace")
    fns = re.findall(r"^def (\w+)\(([^)]*)\)", t, re.M)
    cls = re.findall(r"^class (\w+)", t, re.M)
    print(f"   {p.name:<14} {len(t.splitlines()):>4} 行  classes={cls}")
    for fn, args in fns[:6]:
        print(f"        def {fn}({args[:80]})")
