# -*- coding: utf-8 -*-
r"""只读化迁移 + 检查器（一个脚本两件事）：

  fix     在 `from db_utils import ...` 的上一行插入 `from tcm_ro import use_readonly; use_readonly()`
          （沿用已改好文件的模式；幂等；--apply 才写盘，默认 dry-run 打印计划）
  check   扫描全仓库，列出"还在用 db_utils 且没有 use_readonly 前置"的位置（剩余债）

用法:
  python tools/maintain_db_readonly.py check
  python tools/maintain_db_readonly.py fix            # dry-run
  python tools/maintain_db_readonly.py fix --apply    # 真正修改
"""
from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

STAGE = Path(r"D:\ProgramData\DSHNS\chemreact-staging")
# 演练/快照目录是历史副本（不是活代码），只读化迁移不碰它们
SKIP_DIRS = {"libs", "__pycache__", "reports",
             "migration-rehearsal", "snapshots", "strip-rehearsal"}
SKIP_FILES = {"tcm_ro.py", "maintain_db_readonly.py"}
PAT = re.compile(r"^(\s*)from db_utils import\b")


def iter_py():
    for p in STAGE.rglob("*.py"):
        rel = p.relative_to(STAGE)
        if any(part in SKIP_DIRS for part in rel.parts[:-1]):
            continue
        if p.name in SKIP_FILES:
            continue
        yield p


def scan(path: Path):
    """返回 [(行号(0基), 缩进, 已有前置?)] —— 针对每个 from db_utils import 行。"""
    hits = []
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except Exception:
        return hits
    for i, ln in enumerate(lines):
        if PAT.match(ln):
            prev_ok = any("use_readonly" in lines[j] for j in (i - 1, i - 2) if j >= 0)
            same = "use_readonly" in ln
            hits.append((i, PAT.match(ln).group(1), prev_ok or same))
    return hits


def main() -> int:
    mode = sys.argv[1] if len(sys.argv) > 1 else "check"
    apply_ = "--apply" in sys.argv
    n_todo = n_files = 0
    for p in sorted(iter_py()):
        hits = scan(p)
        todo = [(i, ind) for i, ind, ok in hits if not ok]
        if not todo:
            continue
        n_files += 1
        n_todo += len(todo)
        rel = p.relative_to(STAGE)
        if mode == "check":
            print("  %-52s 待改 %d 处" % (rel, len(todo)))
            continue
        lines = p.read_text(encoding="utf-8", errors="replace").splitlines()
        out, shifted = [], 0
        tset = {i for i, _ in todo}
        for i, ln in enumerate(lines):
            if i in tset:
                m = PAT.match(ln)
                out.append(m.group(1) + "from tcm_ro import use_readonly; use_readonly()")
                shifted += 1
            out.append(ln)
        new_text = "\n".join(out) + "\n"
        try:
            ast.parse(new_text)
        except SyntaxError as ex:
            print("  ★ %s 修改后语法错误，跳过：%s" % (rel, ex))
            continue
        print("  %-52s 插入 %d 处%s" % (rel, len(todo), "" if apply_ else "（dry-run）"))
        if apply_:
            p.write_text(new_text, encoding="utf-8")
    print("文件 %d 个 · 待改 %d 处 · 模式=%s%s"
          % (n_files, n_todo, mode, "（已写盘）" if (mode == "fix" and apply_) else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
