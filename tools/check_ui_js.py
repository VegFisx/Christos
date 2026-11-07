# -*- coding: utf-8 -*-
"""Extract inline <script> blocks from ui_page.html and run `node --check` on each.

Usage:
  python -I tools/check_ui_js.py [path-to-ui_page.html]
"""
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


def _find_node() -> str:
    """找 node：环境变量 NODE_EXE > PATH > 常见安装路径。

    2026-11-04 改：原来写死 C:/Users/Vegfish/.dsh/.../node.exe，
    用户目录改名成 Colorful 后该路径不存在，这个「改完 UI 必跑」的检查器就跑不起来。
    """
    env = os.environ.get("NODE_EXE")
    if env and Path(env).exists():
        return env
    found = shutil.which("node")
    if found:
        return found
    for cand in (r"C:/Program Files/nodejs/node.exe", r"C:/Program Files (x86)/nodejs/node.exe"):
        if Path(cand).exists():
            return cand
    raise SystemExit("找不到 node 可执行文件：请设 NODE_EXE 环境变量，或把 node 加进 PATH")


NODE = _find_node()
HTML = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(
    "D:/ProgramData/DSHNS/chemreact-staging/integration/tcmai_bridge/ui_page.html")
OUT = Path("D:/ProgramData/DSHNS/chemreact-staging/reports/_paozhi_smoke")


def main() -> int:
    html = HTML.read_text(encoding="utf-8")
    blocks = re.findall(r"(?is)<script\b(?![^>]*\bsrc=)[^>]*>(.*?)</script>", html)
    OUT.mkdir(parents=True, exist_ok=True)
    print(f"{HTML}: {len(blocks)} inline script block(s)")
    bad = 0
    for i, block in enumerate(blocks, 1):
        dest = OUT / f"ui_inline_{i}.js"
        dest.write_text(block, encoding="utf-8")
        r = subprocess.run([NODE, "--check", str(dest)], capture_output=True, text=True,
                           encoding="utf-8", errors="replace")
        status = "OK" if r.returncode == 0 else "FAIL"
        print(f"  block {i}: {status} ({len(block)} chars) -> {dest.name}")
        if r.returncode != 0:
            bad += 1
            print((r.stderr or r.stdout or "")[:1200])
    print(f"result: {len(blocks) - bad}/{len(blocks)} block(s) passed")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
