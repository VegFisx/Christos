# -*- coding: utf-8 -*-
"""把产物级候选数据落成一张可直接分析的 parquet（候选级基准表）。

一行 = 一个候选产物；列 = 原始引擎字段 + 29 维数值特征 + 反应级真值/元数据。
特征只从 `tools/train_ranker_v2.py` 取（唯一真源），不在此处重写。

产物：
  reports/candidate_table/candidates_v2.parquet
  reports/candidate_table/meta.json

用法：
  python tools\\build_candidate_table.py
  python tools\\build_candidate_table.py --data reports\\rank_dataset_v2.jsonl
"""
from __future__ import annotations

import argparse
import io
import json
import random
import sys
import time
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

ROOT = Path(__file__).resolve().parents[1]
for _p in (ROOT / "core", ROOT / "tools", ROOT / "conditions", ROOT / "libs"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from rdkit import Chem, RDLogger  # noqa: E402

RDLogger.DisableLog("rdApp.*")

import train_ranker_v2 as TR  # noqa: E402  特征函数的唯一真源

TESTSET = ROOT / "reports" / "paper" / "data" / "uspto50k_canon.jsonl"
DEFAULT_DS = ROOT / "reports" / "rank_dataset_v2.jsonl"
DEFAULT_MODEL = ROOT / "reports" / "rank_model_v2.pkl"
OUT_DIR = ROOT / "reports" / "candidate_table"
SEED = 20261014          # 与 tools/build_rank_dataset.py 的默认 seed 一致

NUM = list(TR.NUM)       # 29 维数值特征，顺序与 train_ranker_v2 一致


def canon(s: str) -> str:
    m = Chem.MolFromSmiles(s) if s else None
    return Chem.MolToSmiles(m) if m is not None else ""


def replay_reactants(n: int) -> tuple:
    """按 build_rank_dataset.py 的洗牌与过滤规则，复原 rid -> 原始测试行。

    返回 (replay, by_want)：
      replay  = {rid: {want, uspto_id, rxn_class, reactants}}
      by_want = {want: {uspto_id, rxn_class, reactants}}（兜底用）
    只做「能建分子 / 产物可规范化」两条便宜的过滤，不跑引擎；
    引擎异常的极少数行会表现为 want 对不上，由 by_want 兜底。
    """
    rows = [json.loads(l) for l in io.open(TESTSET, encoding="utf-8")]
    random.Random(SEED).shuffle(rows)
    replay: dict = {}
    by_want: dict = {}
    rid = 0
    for d in rows[:n]:
        w = canon(d.get("product") or "")
        if not w:
            continue
        info = {
            "uspto_id": d.get("id") or "",
            "rxn_class": str(d.get("class") or ""),
            "reactants": list(d.get("reactants") or []),
        }
        by_want.setdefault(w, info)
        rl = d.get("reactants") or []
        comps = [s for s in rl[:2] if s and Chem.MolFromSmiles(s)]
        if not comps:
            continue
        replay[rid] = dict(info, want=w)
        rid += 1
    return replay, by_want


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default=str(DEFAULT_DS))
    ap.add_argument("--model", default=str(DEFAULT_MODEL))
    ap.add_argument("--out-dir", default=str(OUT_DIR))
    ap.add_argument("--n-replay", type=int, default=12000)
    ap.add_argument("--tag", default="v2", help="输出文件名后缀：candidates_<tag>.parquet")
    a = ap.parse_args()

    import pickle

    import pyarrow as pa
    import pyarrow.parquet as pq

    t0 = time.time()
    data_path = Path(a.data).resolve()
    model_path = Path(a.model).resolve()
    model_obj = pickle.load(io.open(model_path, "rb"))
    top_rules = list(model_obj["top_rules"])
    if list(model_obj["features"]) != NUM + ["rule:" + r for r in top_rules]:
        print("[ERROR] 模型特征表与 train_ranker_v2.NUM 不一致")
        return 2

    print("复原 rid -> 原始测试行 ...", flush=True)
    replay, by_want = replay_reactants(a.n_replay)
    print("  replay 得 %d 行 / want 索引 %d 条（%.0f s）"
          % (len(replay), len(by_want), time.time() - t0), flush=True)

    out_dir = Path(a.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    # 旧名字保持不变（v2），新配置用 _<tag> 后缀，两者并存
    if a.tag == "v2":
        pq_name, meta_name = "candidates_v2.parquet", "meta.json"
    else:
        pq_name, meta_name = ("candidates_%s.parquet" % a.tag,
                              "meta_%s.json" % a.tag)
    pq_path = out_dir / pq_name

    schema = pa.schema(
        [("rid", pa.int32()), ("split", pa.string()), ("want", pa.string()),
         ("rank", pa.int16()), ("label", pa.int8()),
         ("smi", pa.string()), ("rule", pa.string()), ("tpl", pa.string()),
         ("act", pa.float64()), ("sup", pa.int32()), ("eng", pa.float64()),
         ("ext", pa.float64()), ("cur", pa.int8()), ("byp", pa.int8()),
         ("prod_ha", pa.int16()), ("src_ha", pa.int16()), ("keep", pa.float64()),
         ("sub", pa.string()), ("log_sup", pa.float64())]
        + [(c, pa.float64()) for c in NUM[9:]]          # p_* / s_* / d_*
        + [("n_cand", pa.int16()), ("n_pos", pa.int16()), ("true_rank", pa.int16()),
           ("uspto_id", pa.string()), ("rxn_class", pa.string()),
           ("r1", pa.string()), ("r2", pa.string()), ("src_join", pa.string())]
    )
    writer = pq.ParquetWriter(str(pq_path), schema, compression="zstd")

    stats = {"rows": 0, "rids": 0, "pos": 0, "evaluable": 0, "rank0": 0,
             "join_replay": 0, "join_want": 0, "join_none": 0,
             "replay_mismatch": 0, "multi_pos": 0}
    batch: list = []
    cur_rid = None
    buf: list = []

    def flush_group(rid, cands):
        if not cands:
            return
        want = cands[0]["want"]
        split = cands[0].get("split") or "train"
        pos = [c for c in cands if c.get("label") == 1]
        true_rank = min((c["rank"] for c in pos), default=-1)
        n_cand, n_pos = len(cands), len(pos)

        meta = replay.get(rid)
        if meta is not None and meta.get("want") == want:
            src_join = "replay"
        else:
            if meta is not None:
                stats["replay_mismatch"] += 1
            meta = by_want.get(want)
            src_join = "want" if meta else "none"
        stats["join_" + src_join] += 1
        meta = meta or {}
        react = meta.get("reactants") or []

        for c in cands:
            f = TR.feats(c, top_rules)
            rec = {
                "rid": rid, "split": split, "want": want,
                "rank": int(c.get("rank") or 0), "label": int(c.get("label") or 0),
                "smi": c.get("smi") or "", "rule": c.get("rule") or "",
                "tpl": c.get("tpl") or "",
                "act": float(c.get("act") or 0.0), "sup": int(c.get("sup") or 0),
                "eng": float(c.get("eng") or 0.0), "ext": float(c.get("ext") or 0.0),
                "cur": int(c.get("cur") or 0), "byp": int(c.get("byp") or 0),
                "prod_ha": int(c.get("prod_ha") or 0),
                "src_ha": int(c.get("src_ha") or 0),
                "keep": float(c.get("keep") or 0.0),
                "sub": c.get("sub") or "",
                "log_sup": f[1],
                "n_cand": n_cand, "n_pos": n_pos, "true_rank": true_rank,
                "uspto_id": meta.get("uspto_id") or "",
                "rxn_class": str(meta.get("rxn_class") or ""),
                "r1": react[0] if len(react) > 0 else "",
                "r2": react[1] if len(react) > 1 else "",
                "src_join": src_join,
            }
            for name, val in zip(NUM[9:], f[9:len(NUM)]):
                rec[name] = float(val)
            batch.append(rec)
        stats["rows"] += n_cand
        stats["rids"] += 1
        stats["pos"] += n_pos
        stats["evaluable"] += 1 if n_pos else 0
        stats["rank0"] += 1 if true_rank == 0 else 0
        if n_pos > 1:
            stats["multi_pos"] += 1

    print("读候选 %s" % data_path, flush=True)
    with io.open(data_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            if row["rid"] != cur_rid:
                flush_group(cur_rid, buf)
                cur_rid = row["rid"]
                buf = []
            buf.append(row)
            if len(batch) >= 20000:
                writer.write_table(pa.Table.from_pylist(batch, schema=schema))
                batch = []
    flush_group(cur_rid, buf)
    if batch:
        writer.write_table(pa.Table.from_pylist(batch, schema=schema))
    writer.close()

    meta = {
        "built_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "parquet": str(pq_path.relative_to(ROOT)).replace("\\", "/"),
        "source": {
            "candidates": str(data_path.relative_to(ROOT)).replace("\\", "/"),
            "testset": "reports/paper/data/uspto50k_canon.jsonl",
            "model": str(model_path.relative_to(ROOT)).replace("\\", "/"),
        },
        "rebuild": "python tools\\build_candidate_table.py",
        "n_rows": stats["rows"], "n_reactions": stats["rids"],
        "n_evaluable": stats["evaluable"], "n_positive_rows": stats["pos"],
        "recall_any": round(stats["evaluable"] / max(1, stats["rids"]), 6),
        "top1_emission": round(stats["rank0"] / max(1, stats["evaluable"]), 6),
        "multi_positive_reactions": stats["multi_pos"],
        "join": {k: stats[k] for k in ("join_replay", "join_want", "join_none",
                                       "replay_mismatch")},
        "num_features": NUM,
        "top_rules": top_rules,
        "feature_order": NUM + ["rule:" + r for r in top_rules],
        "feature_count": len(NUM) + len(top_rules),
        "columns": {
            "rid": "反应序号（与 rank_dataset_v2.jsonl 相同）",
            "split": "train/test，按 want 的 md5 切分",
            "want": "真产物规范 SMILES（反应级，重复到每行）",
            "rank": "候选在引擎发射序里的位置（0 起）",
            "label": "1 = 该候选等于 want",
            "smi/sub/tpl/rule": "候选产物 / 底物(+partner) / 模板 SMARTS / 规则 id",
            "act/sup/eng/ext/cur/byp": "激活 / 模板支持 / 引擎分 / 进程 / 人工规则 / 副产物",
            "prod_ha/src_ha/keep": "候选重原子 / 底物重原子 / 保留率",
            "log_sup": "log1p(sup)",
            "p_*/s_*/d_*": "产物侧 / 底物侧结构量 / 差值（见 num_features）",
            "n_cand/n_pos/true_rank": "反应级：候选数 / 正例数 / 正例最小 rank（-1=未命中）",
            "uspto_id/rxn_class/r1/r2": "USPTO 专利号 / 反应类 / 前两个反应物 SMILES",
            "src_join": "反应元数据怎么对上的：replay / want / none",
        },
        "notes": [
            "特征只从 tools/train_ranker_v2.py::feats 取，保证与 rank_model_v2.pkl 输入同口径。",
            "30 个规则 one-hot 不在表内，用 meta['top_rules'] 现做，避免 30 列稀疏宽表。",
            "没有正例的反应 true_rank=-1；评估时按 n_pos>0 筛选。",
        ],
        "elapsed_s": round(time.time() - t0, 1),
    }
    (out_dir / meta_name).write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    print("完成：%d 行 / %d 反应 / 可评 %d / 召回 %.4f / 发射序 top-1 %.4f / %.0f s"
          % (stats["rows"], stats["rids"], stats["evaluable"],
             stats["evaluable"] / max(1, stats["rids"]),
             stats["rank0"] / max(1, stats["evaluable"]), time.time() - t0))
    print("写出 %s" % pq_path)
    print("join: replay=%d want=%d none=%d mismatch=%d"
          % (stats["join_replay"], stats["join_want"], stats["join_none"],
             stats["replay_mismatch"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
