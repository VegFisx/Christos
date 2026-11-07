# -*- coding: utf-8 -*-
r"""软著"源程序文档"生成器：自有源码按固定顺序拼接，50 行/页 + 页眉页码；
输出"前 30 页 + 后 30 页"（中间以省略行标注），供转 DOCX/PDF 后提交。"""
from __future__ import annotations

import sys
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

STAGE = Path(r"D:\ProgramData\DSHNS\chemreact-staging")
OUTDIR = STAGE / "reports" / "软著"
NAME = "Christos（炼膏师）化学反应产物预测与药典判据溯源软件"
VERSION = "V1.0.0"
LINES_PER_PAGE = 50
HEAD = 30
TAIL = 30
GROUPS = ["core", "conditions", "rules", "sources", "tools", "integration"]
EXCLUDE_DIRS = ("libs", "__pycache__", "out")
EXTS = (".py", ".html", ".bat")


def collect():
    files = []
    for g in GROUPS:
        base = STAGE / g
        if not base.is_dir():
            continue
        for p in sorted(base.rglob("*")):
            if not p.is_file() or p.suffix not in EXTS:
                continue
            if any(x in p.parts for x in EXCLUDE_DIRS):
                continue
            files.append(p)
    return files


def main() -> int:
    files = collect()
    lines = []
    for p in files:
        rel = p.relative_to(STAGE).as_posix()
        lines.append("# ==================== FILE: %s ====================" % rel)
        try:
            for ln in p.read_text(encoding="utf-8", errors="replace").splitlines():
                lines.append(ln.rstrip())
        except Exception as ex:
            lines.append("# [warn] 读取失败：%s" % ex)
    n_pages = (len(lines) + LINES_PER_PAGE - 1) // LINES_PER_PAGE
    print("文件 %d 个 · 总行 %d · 总页 %d（50 行/页）" % (len(files), len(lines), n_pages))
    OUTDIR.mkdir(parents=True, exist_ok=True)
    outp = OUTDIR / "源程序文档_前30页+后30页.txt"

    def render(page_idx):
        head = "%s %s    第 %d 页" % (NAME, VERSION, page_idx + 1)
        seg = lines[page_idx * LINES_PER_PAGE:(page_idx + 1) * LINES_PER_PAGE]
        return [head, "-" * 60] + seg + [""]

    out = []
    for i in range(min(HEAD, n_pages)):
        out += render(i)
    if n_pages > HEAD + TAIL:
        out.append("……（中间 %d 页略；如需可整体提供）……" % (n_pages - HEAD - TAIL))
    for i in range(max(HEAD, n_pages - TAIL), n_pages):
        out += render(i)
    outp.write_text("\n".join(out), encoding="utf-8")
    print("输出 -> %s（%.1f KB）" % (outp, outp.stat().st_size / 1024))
    return 0


if __name__ == "__main__":
    sys.exit(main())
