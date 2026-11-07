# -*- coding: utf-8 -*-
r"""在【快照副本】上预演剥离，验证方案会不会留下断掉的引用。

★ 绝对不碰 D:\TCMAI
  这个脚本只操作快照复制出来的临时目录：
    snapshots\TCMAI-src-.../   →  临时副本  →  在那里删/改

要回答的问题：
  1. 删掉 3 个纯模块后，哪些文件的 import 会断？
  2. 摘掉纠缠代码后，还剩哪些对已删符号的引用？
  3. 剥离后的代码能不能通过语法检查？
"""
from __future__ import annotations

import ast
import re
import shutil
import sys
from collections import defaultdict
from pathlib import Path

STAGE = Path(r"D:\ProgramData\DSHNS\chemreact-staging")
SNAP_ROOT = STAGE / "snapshots"
WORK = STAGE / "strip-rehearsal"

PURE_DELETE = ["admet_cache.py", "dose_weights.py", "toxic_keywords.py"]

# 纠缠文件里要摘掉的"符号"（按名字识别，比按行号稳）
DROP_SYMBOLS = {
    "tcm_analyzer.py": ["TOXIC_KEYWORDS", "check_toxicity"],
    "coconut_analyzer.py": ["check_toxicity", "TOXIC_KEYWORDS"],
    "visualize.py": ["draw_toxic_report"],
    "batch_pairs.py": ["_admet_summary", "ADMET_KEYS"],
}

OUT_OF_SCOPE_PAT = re.compile(
    r"\btoxic\w*\b|\bhERG\b|\bLD50\b|\bADMET\b|\bAMES\b|\bClinTox\b"
    r"|十八反|十九畏|\bdose_weight\w*\b|\bADMETCache\b",
    re.IGNORECASE)


def latest_snapshot() -> Path:
    snaps = sorted([d for d in SNAP_ROOT.iterdir()
                    if d.is_dir() and (d / "_MANIFEST.json").exists()])
    if not snaps:
        raise SystemExit("没有可用快照")
    return snaps[-1]


def scan_imports(root: Path):
    """扫出每个文件 import 了哪些本地模块。"""
    local = {p.stem for p in root.rglob("*.py")}
    out = defaultdict(set)
    for p in root.rglob("*.py"):
        try:
            tree = ast.parse(p.read_text(encoding="utf-8", errors="ignore"))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for a in node.names:
                    m = a.name.split(".")[0]
                    if m in local:
                        out[p.name].add(m)
            elif isinstance(node, ast.ImportFrom) and node.module:
                m = node.module.split(".")[0]
                if m in local:
                    out[p.name].add(m)
    return out, local


def main() -> int:
    snap = latest_snapshot()
    print(f"快照: {snap.name}")

    if WORK.exists():
        shutil.rmtree(WORK)
    shutil.copytree(snap, WORK)
    # 快照是散装复制，src 在 WORK/src
    src_dir = WORK / "src"
    if not src_dir.is_dir():
        print(f"★ 快照里没有 src/，实际内容: {[p.name for p in WORK.iterdir()]}")
        return 2
    print(f"副本: {WORK}\n")

    before_imports, local = scan_imports(src_dir)
    print(f"src/ 下 {len(local)} 个模块\n")

    # ---------- 第 1 步：删纯模块，看谁断 ----------
    print("=" * 88)
    print("① 删除 3 个纯模块后，谁会断（模拟）")
    print("=" * 88)
    broken = defaultdict(list)
    for f, mods in sorted(before_imports.items()):
        for m in mods:
            if f"{m}.py" in PURE_DELETE:
                broken[f].append(m)
    if broken:
        for f, mods in sorted(broken.items()):
            print(f"  {f:<28} 依赖 {sorted(mods)}")
    else:
        print("  （无）")

    # ---------- 第 2 步：缠结文件里还引用哪些已删符号 ----------
    print()
    print("=" * 88)
    print("② 缠结文件里，对已删符号的引用")
    print("=" * 88)
    dropped_names = {"check_toxicity", "ADMETCache"}
    for f in sorted(DROP_SYMBOLS):
        p = src_dir / f
        if not p.exists():
            continue
        txt = p.read_text(encoding="utf-8", errors="ignore")
        hits = []
        for i, line in enumerate(txt.splitlines(), 1):
            if any(n in line for n in dropped_names):
                hits.append((i, line.strip()[:76]))
        print(f"\n  【{f}】{len(hits)} 处")
        for i, l in hits[:8]:
            print(f"    {i:>4}: {l}")
        if len(hits) > 8:
            print(f"    … 另有 {len(hits)-8} 处")

    # ---------- 第 3 步：不在范围内的代码总量 ----------
    print()
    print("=" * 88)
    print("③ 「不在范围内」的代码在 src/ 里的总量")
    print("=" * 88)
    total = 0
    per_file = []
    for p in sorted(src_dir.rglob("*.py")):
        n = 0
        for line in p.read_text(encoding="utf-8", errors="ignore").splitlines():
            s = line.strip()
            if s.startswith("#"):
                continue
            if OUT_OF_SCOPE_PAT.search(line):
                n += 1
        if n:
            per_file.append((n, p.name))
            total += n
    for n, name in sorted(per_file, reverse=True):
        flag = " ← 整体删除" if name in PURE_DELETE else ""
        print(f"  {n:>4} 行  {name}{flag}")
    print(f"\n  合计 {total} 行（占 src/ 全部行数的比例见下）")
    all_lines = sum(len(p.read_text(encoding='utf-8', errors='ignore').splitlines())
                    for p in src_dir.rglob("*.py"))
    print(f"  src/ 总行数 {all_lines}，不在范围内占 {100*total/max(1,all_lines):.1f}%")

    # ---------- 第 4 步：真删一次，验证语法 ----------
    print()
    print("=" * 88)
    print("④ 真删一次（只在副本上），验证语法是否还通")
    print("=" * 88)
    for name in PURE_DELETE:
        p = src_dir / name
        if p.exists():
            p.unlink()
            print(f"  已删 {name}")
        else:
            print(f"  跳过（副本里没有）{name}")

    ok = bad = 0
    for p in sorted(src_dir.rglob("*.py")):
        try:
            ast.parse(p.read_text(encoding="utf-8", errors="ignore"))
            ok += 1
        except SyntaxError as e:
            bad += 1
            print(f"  ★语法错误 {p.name}: {e}")
    print(f"\n  语法检查：{ok} 个通过 / {bad} 个失败")
    print("  （注意：删模块【不会】造成语法错误，只会造成 import 失败——")
    print("    所以要跑 import 扫描，见 ①）")

    print()
    print("=" * 88)
    print("结论")
    print("=" * 88)
    print(f"""
  需要人工改的文件：{len(broken)} 个（见 ①）
  需要摘除的缠结引用：见 ②

  ★ 副本保留在 {WORK}
    只是预演，D:\\TCMAI 一个字节都没动。
""")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
