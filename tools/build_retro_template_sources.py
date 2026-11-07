# -*- coding: utf-8 -*-
r"""第四十三轮：逆模板「出处还原」—— 每条聚类模板来自哪些 ORD 反应。

背景：reports/retro_templates_clustered.jsonl（3,228 条）只有 template/fp/freq 三个字段，
没有"原始反应出处"；而抽取分片 reports/_shard_[0-9].jsonl 里每条都带 rx（完整映射反应，
形如 反应物>>产物）。两边按 template 精确连接即可还原出处；加 --with-rxn-ids 时再扫一遍
本地 ORD parquet，把 rx 反查成 reaction_id。

输出：reports/retro_template_sources.jsonl（每模板一行）：
  {template, fp, freq, n_instances, sources:[{shard, rx}...最多 3 条], reaction_ids, n_rxn_ids}

用法：
  python tools/build_retro_template_sources.py                 # 只用分片（快）
  python tools/build_retro_template_sources.py --with-rxn-ids  # 额外扫 ORD parquet 反查 id
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

STAGE = Path(r"D:\ProgramData\DSHNS\chemreact-staging")
REPORTS = STAGE / "reports"
BIG = STAGE / "ord-data" / "data" / "11" / \
    "ord_dataset-1158e351757f315b93cbcbe7bc55f38e.parquet"
CLUSTERED = REPORTS / "retro_templates_clustered.jsonl"
OUT = REPORTS / "retro_template_sources.jsonl"
MAX_SRC = 3

# --with-rxn-ids 需要 duckdb + ord_schema：两者在 libs/（cp312）里，须用 Python 3.12 跑
# （项目 venv：D:\TCMAI\venv\Scripts\python.exe；protobuf 运行时在 venv 里）
if str(STAGE / "libs") not in sys.path:
    sys.path.insert(0, str(STAGE / "libs"))


def norm_cx(cx: str):
    """把 ORD 的 CXSMILES 归一成分片 rx 的同款写法（与 retro_extract_shard.py 一致）。"""
    if not cx:
        return None
    body = cx.split("|", 1)[0] if "|" in cx else cx
    parts = body.split(">")
    if len(parts) == 2:
        lhs, rhs = parts
    elif len(parts) == 3:
        lhs, _m, rhs = parts
    else:
        return None
    rs_ = [p for p in lhs.split(".") if p.strip()]
    ps = [p for p in rhs.split(".") if p.strip()]
    if not rs_ or not ps:
        return None
    return ".".join(rs_) + ">>" + ".".join(ps)


def load_shards():
    per_template = {}
    counts = {}
    n_lines = 0
    shard_files = sorted(REPORTS.glob("_shard_[0-9].jsonl"))
    for sp in shard_files:
        with open(sp, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    r = json.loads(line)
                except Exception:
                    continue
                n_lines += 1
                t = str(r.get("template") or "")
                if not t:
                    continue
                counts[t] = counts.get(t, 0) + 1
                ent = per_template.setdefault(t, [])
                if len(ent) < MAX_SRC:
                    ent.append({"shard": sp.name, "rx": str(r.get("rx") or "")})
    return shard_files, per_template, counts, n_lines


def main() -> int:
    t0 = time.time()
    with_ids = "--with-rxn-ids" in sys.argv
    print("=" * 78)
    print("逆模板出处还原：clustered 与抽取分片对齐"
          + ("（含 reaction_id 反查）" if with_ids else ""))
    print("=" * 78)

    shard_files, per_template, counts, n_lines = load_shards()
    print("分片 %d 个 · 抽取记录 %d 条 · 去重模板 %d 条（%.1fs）"
          % (len(shard_files), n_lines, len(per_template), time.time() - t0), flush=True)

    clustered = []
    with open(CLUSTERED, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                clustered.append(json.loads(line))

    rows = []
    n_with_src = 0
    for r in clustered:
        t = str(r.get("template") or "")
        src = per_template.get(t, [])
        if src:
            n_with_src += 1
        rows.append({"template": t, "fp": r.get("fp", ""), "freq": r.get("freq"),
                     "n_instances": counts.get(t, 0), "sources": src,
                     "reaction_ids": [], "n_rxn_ids": 0})
    print("clustered %d 条 · 能对上出处的 %d 条（%.1f%%）"
          % (len(rows), n_with_src, 100.0 * n_with_src / max(1, len(rows))), flush=True)

    if with_ids:
        need = {x["rx"] for row in rows for x in row["sources"]}
        print("反查 reaction_id：待匹配 rx 唯一串 %d 条；读 %s ..."
              % (len(need), BIG.name), flush=True)
        try:
            import duckdb
            from ord_schema.proto import reaction_pb2
            con = duckdb.connect()
            con.execute("SET threads=1")
            cur = con.execute(
                f"SELECT reaction_id, reaction FROM read_parquet('{BIG.as_posix()}')")
            rx2id = {}
            n_seen = n_bad = 0
            while True:
                batch = cur.fetchmany(5000)
                if not batch:
                    break
                for rid, blob in batch:
                    n_seen += 1
                    try:
                        rxn = reaction_pb2.Reaction()
                        rxn.ParseFromString(blob)
                        cx = next((i.value for i in rxn.identifiers
                                   if i.type == reaction_pb2.ReactionIdentifier.REACTION_CXSMILES
                                   and i.value), None)
                    except Exception:
                        n_bad += 1
                        continue
                    if not cx:
                        continue
                    k = norm_cx(cx)
                    if k and k in need and k not in rx2id:
                        rx2id[k] = rid
                if n_seen % 50000 == 0:
                    print("   ... 已扫 %d 条，命中 %d" % (n_seen, len(rx2id)), flush=True)
            print("ORD 扫描：%d 条（解析失败 %d）· rx 命中 %d/%d（%.1fs）"
                  % (n_seen, n_bad, len(rx2id), len(need), time.time() - t0), flush=True)
            for row in rows:
                ids = []
                for x in row["sources"]:
                    rid = rx2id.get(x["rx"])
                    if rid and rid not in ids:
                        ids.append(rid)
                row["reaction_ids"] = ids
                row["n_rxn_ids"] = len(ids)
        except Exception as ex:                       # noqa: BLE001 —— 打印，不静默
            print("   [warn] reaction_id 反查失败：%s: %s" % (type(ex).__name__, ex))

    with open(OUT, "w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    if with_ids:
        n_ids = sum(1 for row in rows if row["n_rxn_ids"] > 0)
        print("有 reaction_id 的模板：%d/%d（%.1f%%）"
              % (n_ids, len(rows), 100.0 * n_ids / max(1, len(rows))))
    print("写出：%s（%d 行，%.1f KB）" % (OUT.name, len(rows), OUT.stat().st_size / 1024))
    for row in rows[:3]:
        print("  样例：n_instances=%s sources=%d ids=%s"
              % (row["n_instances"], len(row["sources"]), row["reaction_ids"][:2]))
    print("总耗时 %.1fs" % (time.time() - t0))
    return 0


if __name__ == "__main__":
    sys.exit(main())
