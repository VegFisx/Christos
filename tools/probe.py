# -*- coding: utf-8 -*-
r"""
数据结构探测器 —— 只回报【结构】，不回报【内容】
================================================

★ 为什么要有这个

  用户指出的问题（完全正确）：
    查数据库/大文件时，应该【写脚本让脚本告诉你结构】，
    而不是直接把内容读进上下文。又慢又费 token。

  我犯过的实例：
    · dump 了 887 KB 的配置 schema，只为看一个字段名
    · 读了 121 MB 的 app.asar
    · 直接 read 配置文件

★ 设计原则

  1. 输出【永远】控制在 ~40 行以内
  2. 只回答"这是什么形状"，不回答"里面写了什么"
  3. 支持 csv / parquet / json / jsonl / yaml / sqlite / 目录 / 纯文本
  4. 每种格式给：类型、规模、字段、少量样例

用法：
    python tools\probe.py <路径> [--rows 3] [--cols 20]
    python tools\probe.py D:\TCMAI\tcm.db
    python tools\probe.py D:\TCMAI\docs\supplementary\TableS1_reaction_rules.csv
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
from pathlib import Path

MAX_LINES = 46          # 硬上限，防止脚本自己刷屏


def _out(buf, s=""):
    buf.append(str(s))


def human(n: int) -> str:
    for u in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024:
            return f"{n:.1f} {u}"
        n /= 1024
    return f"{n:.1f} PB"


def probe_csv(p: Path, buf, rows=3, max_cols=25):
    import csv
    with p.open(encoding="utf-8-sig", errors="replace", newline="") as f:
        r = csv.reader(f)
        try:
            hdr = next(r)
        except StopIteration:
            _out(buf, "  空文件")
            return
        n = sum(1 for _ in r)
    _out(buf, f"  列数 {len(hdr)}   数据行 {n}")
    _out(buf, f"  列名: {hdr[:max_cols]}")


def probe_parquet(p: Path, buf, rows=3, max_cols=25):
    try:
        import pyarrow.parquet as pq
    except ImportError:
        _out(buf, "  (需要 pyarrow)")
        return
    f = pq.ParquetFile(p)
    md = f.metadata
    _out(buf, f"  行数 {md.num_rows}   列数 {md.num_columns}   "
              f"行组 {md.num_row_groups}")
    names = f.schema_arrow.names
    _out(buf, f"  列名: {names[:max_cols]}")
    _out(buf, "  类型:")
    for nm, ty in list(zip(names, f.schema_arrow.types))[:max_cols]:
        _out(buf, f"      {nm:<28}{ty}")
    t = f.read_row_group(0).slice(0, rows)
    _out(buf, f"  前 {min(rows, t.num_rows)} 行:")
    for row in t.to_pylist()[:rows]:
        _out(buf, "      " + json.dumps(row, ensure_ascii=False,
                                        default=str)[:150])


def probe_json(p: Path, buf, rows=3, max_cols=25):
    with p.open(encoding="utf-8", errors="replace") as f:
        head = f.read(4096)
    try:
        j = json.loads(p.read_text(encoding="utf-8", errors="replace"))
    except Exception as e:
        _out(buf, f"  解析失败: {type(e).__name__}（可能是 JSONL 或超大文件）")
        _out(buf, f"  开头: {head[:150]!r}")
        return

    def shape(o, depth=0, label="$", limit=3):
        pad = "  " * (depth + 1)
        if isinstance(o, dict):
            _out(buf, f"  {pad}{label}: dict({len(o)} 键)")
            if depth < 2:
                for k in list(o)[:limit]:
                    shape(o[k], depth + 1, str(k), limit)
        elif isinstance(o, list):
            _out(buf, f"  {pad}{label}: list({len(o)})")
            if depth < 2 and o:
                shape(o[0], depth + 1, "[0]", limit)
        else:
            v = repr(o)
            _out(buf, f"  {pad}{label}: {type(o).__name__} = {v[:60]}")
    shape(j)


def probe_jsonl(p: Path, buf, rows=3, max_cols=25):
    n = 0
    first = None
    with p.open(encoding="utf-8", errors="replace") as f:
        for line in f:
            n += 1
            if first is None and line.strip():
                try:
                    first = json.loads(line)
                except Exception:
                    first = None
    _out(buf, f"  行数 {n}")
    if isinstance(first, dict):
        _out(buf, f"  每行键: {list(first)[:max_cols]}")
        _out(buf, f"  首行样例: {json.dumps(first, ensure_ascii=False)[:180]}")


def probe_yaml(p: Path, buf, rows=3, max_cols=25):
    try:
        import yaml
        j = yaml.safe_load(p.read_text(encoding="utf-8", errors="replace"))
    except Exception as e:
        _out(buf, f"  解析: {type(e).__name__} —— 退回纯文本统计")
        probe_text(p, buf)
        return
    if isinstance(j, list):
        _out(buf, f"  顶层: 列表 {len(j)} 项")
        for i, it in enumerate(j[:6]):
            if isinstance(it, dict):
                _out(buf, f"      [{i}] 键: {list(it)[:8]}")
            else:
                _out(buf, f"      [{i}] {type(it).__name__} {str(it)[:50]}")
    elif isinstance(j, dict):
        _out(buf, f"  顶层: 字典 {len(j)} 键: {list(j)[:max_cols]}")
    else:
        _out(buf, f"  顶层: {type(j).__name__}")


def probe_sqlite(p: Path, buf, rows=3, max_cols=25):
    con = sqlite3.connect(f"file:{p}?mode=ro", uri=True)
    cur = con.cursor()
    cur.execute("SELECT name,type FROM sqlite_master WHERE type IN "
                "('table','view') ORDER BY name")
    objs = cur.fetchall()
    _out(buf, f"  表/视图 {len(objs)} 个")
    for name, typ in objs[:12]:
        try:
            cur.execute(f'SELECT COUNT(*) FROM "{name}"')
            cnt = cur.fetchone()[0]
        except Exception:
            cnt = "?"
        cur.execute(f'PRAGMA table_info("{name}")')
        cols = [r[1] for r in cur.fetchall()]
        _out(buf, f"      {typ:<6}{name:<28}{str(cnt):>10} 行   "
                  f"列 {cols[:max_cols]}")
    con.close()


def probe_text(p: Path, buf, rows=3, max_cols=25):
    n = 0
    longest = 0
    with p.open(encoding="utf-8", errors="replace") as f:
        for line in f:
            n += 1
            longest = max(longest, len(line))
            if n >= 200000:
                break
    _out(buf, f"  行数 {'>=200000' if n >= 200000 else n}   最长行 {longest} 字符")
    with p.open(encoding="utf-8", errors="replace") as f:
        for i, line in enumerate(f):
            if i >= rows:
                break
            _out(buf, f"      行{i+1}: {line.rstrip()[:120]}")


def probe_dir(p: Path, buf, rows=3, max_cols=25):
    items = list(p.iterdir())
    files = [x for x in items if x.is_file()]
    dirs = [x for x in items if x.is_dir()]
    total = sum(x.stat().st_size for x in files)
    _out(buf, f"  文件 {len(files)} 个（{human(total)}）  子目录 {len(dirs)} 个")
    from collections import Counter
    ext = Counter(x.suffix.lower() or "(无扩展名)" for x in files)
    _out(buf, f"  扩展名分布: {dict(ext.most_common(10))}")
    _out(buf, f"  子目录: {[x.name for x in dirs][:max_cols]}")
    _out(buf, "  最大的几个文件:")
    for x in sorted(files, key=lambda y: -y.stat().st_size)[:6]:
        _out(buf, f"      {human(x.stat().st_size):>10}  {x.name}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("path")
    ap.add_argument("--rows", type=int, default=3)
    ap.add_argument("--cols", type=int, default=25)
    a = ap.parse_args()

    p = Path(a.path)
    buf = []
    if not p.exists():
        print(f"路径不存在: {p}")
        return 1

    _out(buf, "=" * 70)
    _out(buf, f"{p}")
    if p.is_file():
        _out(buf, f"  大小 {human(p.stat().st_size)}")
    _out(buf, "=" * 70)

    if p.is_dir():
        probe_dir(p, buf, a.rows, a.cols)
    else:
        ext = p.suffix.lower()
        try:
            if ext == ".csv":
                probe_csv(p, buf, a.rows, a.cols)
            elif ext in (".parquet", ".pq"):
                probe_parquet(p, buf, a.rows, a.cols)
            elif ext in (".db", ".sqlite", ".sqlite3"):
                probe_sqlite(p, buf, a.rows, a.cols)
            elif ext == ".json":
                probe_json(p, buf, a.rows, a.cols)
            elif ext in (".jsonl", ".ndjson"):
                probe_jsonl(p, buf, a.rows, a.cols)
            elif ext in (".yml", ".yaml"):
                probe_yaml(p, buf, a.rows, a.cols)
            else:
                # 按内容嗅探
                head = p.read_bytes()[:512]
                if head[:15] == b"SQLite format 3":
                    probe_sqlite(p, buf, a.rows, a.cols)
                elif head.lstrip()[:1] in (b"{", b"["):
                    probe_json(p, buf, a.rows, a.cols)
                else:
                    probe_text(p, buf, a.rows, a.cols)
        except Exception as e:
            _out(buf, f"  探测失败: {type(e).__name__}: {e}")

    out = buf[:MAX_LINES]
    if len(buf) > MAX_LINES:
        out.append(f"  …（已截断，共 {len(buf)} 行）")
    print("\n".join(out))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
