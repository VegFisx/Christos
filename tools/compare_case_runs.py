# -*- coding: utf-8 -*-
r"""对比两次验收用例运行的**逐条结果**（第七十五轮 H3 的护栏②）。

用法：``python tools\compare_case_runs.py 基线.txt 改后.txt``

判定：逐条用例的 通过/失败 必须**完全一致**；
有任何一条从 ✓ 变 ✗（或反过来），打印出来并退出码 1 —— 那种差异必须逐条解释清楚。
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

LINE = re.compile(r"^([✓✗])\s+(\S+)")


def read_text(p: Path) -> str:
    """PowerShell 的 ``>`` 重定向会写 UTF-16LE，所以这里先嗅探编码再读。"""
    raw = p.read_bytes()
    for enc in ("utf-8-sig", "utf-16", "utf-8", "gbk"):
        try:
            t = raw.decode(enc)
        except UnicodeDecodeError:
            continue
        if "用例" in t or "✓" in t or "✗" in t or "通过" in t:
            return t
    return raw.decode("utf-8", errors="replace")


def parse(p: Path) -> dict:
    out = {}
    for ln in read_text(p).splitlines():
        m = LINE.match(ln.strip())
        if m:
            out[m.group(2)] = ("通过" if m.group(1) == "✓" else "失败")
    return out


def main() -> int:
    if len(sys.argv) < 3:
        print("用法：python tools\\compare_case_runs.py 基线.txt 改后.txt")
        return 2
    a, b = parse(Path(sys.argv[1])), parse(Path(sys.argv[2]))
    print("=" * 96)
    print("逐条一致性对比")
    print("=" * 96)
    print("  基线 %d 条 ｜ 改后 %d 条" % (len(a), len(b)))
    only_a = sorted(set(a) - set(b))
    only_b = sorted(set(b) - set(a))
    diff = sorted(k for k in set(a) & set(b) if a[k] != b[k])
    n_pass_a = sum(1 for v in a.values() if v == "通过")
    n_pass_b = sum(1 for v in b.values() if v == "通过")
    print("  通过：基线 %d ｜ 改后 %d" % (n_pass_a, n_pass_b))
    if only_a:
        print("  ★ 只在基线里出现的用例 %d 条：%s" % (len(only_a), only_a[:5]))
    if only_b:
        print("  ★ 只在改后里出现的用例 %d 条：%s" % (len(only_b), only_b[:5]))
    if diff:
        print("  ★ 结果翻转的用例 %d 条：" % len(diff))
        for k in diff:
            print("      %-30s 基线=%s  改后=%s" % (k, a[k], b[k]))
    else:
        print("  ✓ 所有同名用例的通过/失败**完全一致**（0 处翻转）")
    ok = not diff and not only_a and not only_b
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
