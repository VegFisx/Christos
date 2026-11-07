# -*- coding: utf-8 -*-
r"""探查 smartreact 的 templates.txt 结构（只打印形状 + 少量样例截断）。"""
import sys
from collections import Counter
from pathlib import Path

P = Path(r"D:\ProgramData\DSHNS\chemreact-staging\libs\smartreact\data\templates.txt")
print("=" * 78)
print(f"文件: {P}")
print(f"大小: {P.stat().st_size/1024**2:.2f} MB")
print("=" * 78)

lines = P.read_text(encoding="utf-8", errors="replace").splitlines()
print(f"总行数: {len(lines)}")
print(f"\n第 1 行 (表头?, 截断 300 字符):")
print("  " + lines[0][:300])
print(f"\n第 2 行 (截断 300 字符):")
print("  " + lines[1][:300] if len(lines) > 1 else "  -")
print(f"\n第 3 行 (截断 300 字符):")
print("  " + lines[2][:300] if len(lines) > 2 else "  -")

# 分隔符判断
head = lines[0]
print("\n" + "=" * 78)
print("分隔符候选")
print("=" * 78)
for sep, name in [("\t", "TAB"), ("|", "PIPE"), (";", "SEMI"), (",", "COMMA")]:
    print(f"  {name:<6} 首行出现 {head.count(sep)} 次")

# 按 TAB 试拆
sep = "\t" if head.count("\t") >= 4 else ("|" if head.count("|") >= 4 else None)
print(f"\n选用分隔符: {sep!r}")
if sep:
    cols = head.split(sep)
    print(f"列数: {len(cols)}")
    for i, c in enumerate(cols):
        print(f"  [{i}] {c}")

    print("\n" + "=" * 78)
    print("逐列取值分布（数据行）")
    print("=" * 78)
    data = [l.split(sep) for l in lines[1:] if l.strip()]
    nr = Counter(len(r) for r in data)
    print(f"  数据行 {len(data)} 行，列数分布: {dict(nr)}")

    # 反应类型列（假设第 0 列）
    c0 = Counter(r[0] for r in data if r)
    print(f"\n  第 0 列唯一值 {len(c0)} 个，前 12:")
    for k, v in c0.most_common(12):
        print(f"      {v:>5}  {k}")

    # example 列：看形状
    if len(cols) > 2:
        print(f"\n  第 2 列（example?）形状:")
        ex = [r[2] for r in data if len(r) > 2 and r[2].strip()]
        print(f"      非空 {len(ex)} 条")
        c_arrow = Counter(">>" in e for e in ex)
        print(f"      含 '>>' 的: {dict(c_arrow)}")
        c_dot = Counter("." in e.split(">>")[0] if ">>" in e else False for e in ex)
        print(f"      '>>' 左侧含 '.'（多底物）: {dict(c_dot)}")
        print("      样例 3 条（截断 120）:")
        for e in ex[:3]:
            print(f"          {e[:120]}")
