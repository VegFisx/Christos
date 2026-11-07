# -*- coding: utf-8 -*-
r"""E-1 / 第十二轮：从 ORD 统计【辅助试剂覆盖率】——哪个试剂是这类反应的"必需件"。

为什么需要：条件表的 auxiliary_reagents 只有名字（top-10），没有覆盖率，
           无法判断 PPh3 是"必需"还是"偶尔用"，也无法做「缺 DEAD 就判零」。

口径（与 build_condition_table.py 同一口径，别改）：
  辅助试剂 = ORD 里【声明为 REACTANT、但原子没进产物】的组分
  覆盖率   = 该试剂出现的反应数 / 该类反应总数（分母 = 成功归类的反应数）
  必需件   = 覆盖率 >= 0.5 ；可选件 = 0.15 <= 覆盖率 < 0.5

两种模式：
  单进程：python extract_aux_reagent_coverage.py [最大反应数]
  分片  ：python extract_aux_reagent_coverage.py --shard <offset> <n> <out.json>
          ★ 推荐走并行总控：python run_aux_reagent_coverage.py
          （原单进程版逐条 enumerate_pair，实测 20000 条要十几分钟；
            分片是工作区已验证的做法：独立进程，躲开"个别分子挂死整池"的坑）

第十二轮的两处改动，都是纪律要求：
  1. 分片支持（提速）；
  2. 原来每一处 `continue` 都是静默跳过 —— 现在全部进 stat 计数并打印，
     否则"分类失败 340 次"会被当成"这类反应就是少"（AGENTS.md 第六节第 4 条）。
"""
import json
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

STAGE = Path(r"D:\ProgramData\DSHNS\chemreact-staging")
sys.path.insert(0, str(STAGE / "libs"))
sys.path.insert(0, str(STAGE / "tools"))

import duckdb  # noqa: E402
from rdkit import Chem, RDLogger  # noqa: E402
from ord_schema.proto import reaction_pb2  # noqa: E402

RDLogger.DisableLog("rdApp.*")
BIG = STAGE / "ord-data" / "data" / "11" / \
    "ord_dataset-1158e351757f315b93cbcbe7bc55f38e.parquet"
OUT = STAGE / "reports" / "aux_reagent_coverage.json"
TEMPLATES = STAGE / "libs" / "smartreact" / "data" / "templates.txt"

REQUIRED_COV = 0.5     # 必需件阈值
OPTIONAL_COV = 0.15    # 可选件阈值


def load_name_map():
    """模板 SMARTS -> 反应类型名（用于把反应归到 37 类）。"""
    m = {}
    for line in TEMPLATES.read_text(encoding="utf-8", errors="replace").splitlines()[1:]:
        f = line.split("\t")
        if len(f) != 5 or ">>" not in f[3]:
            continue
        m[f[3]] = f[0]
    return m


def atom_map_set(smi):
    """SMILES 里出现的映射号集合。"""
    out = set()
    i = 0
    while True:
        j = smi.find(":", i)
        if j < 0:
            break
        k = j + 1
        num = ""
        while k < len(smi) and smi[k].isdigit():
            num += smi[k]
            k += 1
        if num:
            out.add(int(num))
        i = k
    return out


def canon_nomap(smi):
    """去映射后的 canonical SMILES（失败返回 None）。

    ★ 第十二轮：这里必须用 isomericSmiles=False ★
    实测（tools/probe_canon_variants.py，10 万条）：
      DEAD 写成 "CCOC(=O)/N=N/C(=O)OCC"（有立体）与 "CCOC(=O)N=NC(=O)OCC"（无立体）
      在保立体下是【两个不同的桶】：111 条 vs 121 条；去立体后合并为 232 条。
      DIAD 同理：67 + 69 -> 136。
    后果（修复前的实测数字）：mitsunobu 里 PPh3 覆盖 59%（无立体，不受影响），
      而 DEAD 只有 18% —— 于是"缺 DEAD 判零"这条判据被错杀成"数据不支持"。
    对"某试剂是不是这类反应的必需件"来说，E/Z 写法不该算两个试剂。
    """
    m = Chem.MolFromSmiles(smi)
    if m is None:
        return None
    for a in m.GetAtoms():
        a.SetAtomMapNum(0)
    return Chem.MolToSmiles(m, isomericSmiles=False)


def classify(blob, enum, stat):
    """一条 ORD 反应 -> (reaction_name, [辅助试剂 canonical SMILES])；归类失败返回 (None, None)。

    所有失败路径都计数到 stat（不许静默 continue）。
    """
    rxn = reaction_pb2.Reaction()
    try:
        rxn.ParseFromString(blob)
    except Exception:
        stat["protobuf解析失败"] += 1
        return None, None
    cx = next((i.value for i in rxn.identifiers
               if i.type == reaction_pb2.ReactionIdentifier.REACTION_CXSMILES and i.value),
              None)
    if not cx:
        stat["无CXSMILES"] += 1
        return None, None
    body = cx.split("|", 1)[0] if "|" in cx else cx
    parts = body.split(">")
    if len(parts) == 2:
        lhs, rhs = parts
    elif len(parts) == 3:
        lhs, _m, rhs = parts
    else:
        stat["段数异常"] += 1
        return None, None
    rs = [p for p in lhs.split(".") if p.strip()]
    ps = [p for p in rhs.split(".") if p.strip()]
    if not rs or not ps:
        stat["空侧"] += 1
        return None, None
    if len(ps) != 1:
        stat[f"产物数={len(ps)}"] += 1
        return None, None
    prod_maps = atom_map_set(ps[0])
    if not prod_maps:
        stat["产物无映射"] += 1
        return None, None
    contributors = [r for r in rs if atom_map_set(r) & prod_maps]
    if not contributors:
        stat["无反应物原子进产物"] += 1
        return None, None
    if len(contributors) > 2:
        stat["贡献者>2"] += 1
        return None, None
    aux = [r for r in rs if r not in contributors]
    if len(contributors) == 2:
        try:
            res = enum.enumerate_pair(contributors[0], contributors[1])
        except Exception:
            stat["枚举抛异常"] += 1
            return None, None
    else:
        stat["单反应物(不归类)"] += 1
        return None, None
    name = None
    try:
        m2 = Chem.MolFromSmiles(ps[0])
        if m2 is None:
            stat["产物SMILES非法"] += 1
            return None, None
        for a in m2.GetAtoms():
            a.SetAtomMapNum(0)
        want = Chem.MolToSmiles(m2)
    except Exception:
        stat["产物规范化失败"] += 1
        return None, None
    for r in res:
        for p in r.products:
            m1 = Chem.MolFromSmiles(p)
            if m1 is None:
                continue
            for a in m1.GetAtoms():
                a.SetAtomMapNum(0)
            if Chem.MolToSmiles(m1) == want:
                name = r.reaction_name
                break
        if name:
            break
    if not name:
        stat["未匹配到37类模板"] += 1
        return None, None
    aux_canon = []
    for a in aux:
        cs = canon_nomap(a)
        if cs:
            aux_canon.append(cs)
        else:
            stat["辅助试剂SMILES非法"] += 1
    # ★ 同一反应内按分子去重 ★
    #   实测教训：K2CO3 在 CXSMILES 里是 "O=C([O-])[O-].[K+].[K+]"，
    #   拆开后 [K+] 出现两次 -> 覆盖率能算到 126%（ART n=54 实测）。
    return name, sorted(set(aux_canon))


def accumulate(rows, enum, verbose=True, log_every=5000):
    """跑一批行，返回 (total, aux_hits, stat, n_done)。失败全部计数，不静默。"""
    total = Counter()
    aux_hits = defaultdict(Counter)
    stat = Counter()
    n_done = 0
    t0 = time.time()
    for (blob,) in rows:
        n_done += 1
        try:
            name, aux = classify(blob, enum, stat)
        except Exception as e:                      # 兜底也要计数，别吞
            stat[f"未预期异常:{type(e).__name__}"] += 1
            continue
        if not name:
            continue
        total[name] += 1
        for cs in aux:
            aux_hits[name][cs] += 1
        if verbose and log_every and n_done % log_every == 0:
            print(f"   {n_done:,} 条  已归类 {sum(total.values()):,}  "
                  f"{time.time()-t0:.0f}s", flush=True)
    return total, aux_hits, stat, n_done


def summarize(total, aux_hits, out_path=OUT, print_top=True, top_n=40):
    """覆盖率 -> 必需件/可选件，写 JSON，打印摘要。

    ★ 两个口径修正（第十三轮，全量跑完后发现）★
    1. top_n 从 12 放宽到 40：只存 top-12 时，**角色归并会失效** ——
       实测 suzuki（n=41,470）的 top-12 全被 [Na+]/[K+] 这类反离子占满，
       碳酸根/磷酸根碎片排在 12 名之后被截掉，于是"按角色相加"凑不出"需要碱"。
       （分片件里有完整计数器，所以改完只需 `--merge-only` 重算，不必重扫。）
    2. 覆盖率截到 1.0：同一反应内同一碎片出现两次会重复计数（实测 ART 的 [K+] 到 126%）。
       根因已在 accumulate() 里修（按反应去重），但本次表格是在修复前扫的，
       这里做保守截断，避免 >100% 的荒谬数字进判据。
    """
    result = {}
    for name, n in total.items():
        cov = [(smi, min(1.0, c / n)) for smi, c in aux_hits[name].most_common(top_n)]
        result[name] = {
            "n_reactions": n,
            "required": [{"smiles": s, "coverage": round(v, 3)}
                         for s, v in cov if v >= REQUIRED_COV],
            "optional": [{"smiles": s, "coverage": round(v, 3)}
                         for s, v in cov if OPTIONAL_COV <= v < REQUIRED_COV],
        }
    Path(out_path).write_text(json.dumps(result, ensure_ascii=False, indent=2),
                              encoding="utf-8")
    if print_top:
        print()
        print("=" * 96)
        print(f"每类的必需件（覆盖率 >= {REQUIRED_COV}）")
        print("=" * 96)
        for name in sorted(result, key=lambda k: -result[k]["n_reactions"]):
            e = result[name]
            if not e["required"]:
                continue
            req = ", ".join(f"{r['smiles'][:34]}({r['coverage']:.0%})"
                            for r in e["required"][:4])
            print(f"  {name[:28]:<30} n={e['n_reactions']:<6} 必需: {req}")
        n_req = sum(1 for e in result.values() if e["required"])
        print(f"\n  有必需件的类型: {n_req}/{len(result)}")
        print(f"  -> {Path(out_path).name}")
    return result


def shard_main(off, n, out_path):
    from smartreact import ReactionEnumerator
    t0 = time.time()
    enum = ReactionEnumerator()
    con = duckdb.connect()
    con.execute("SET memory_limit='500MB'")
    con.execute("SET threads=1")
    rows = con.execute(
        f"SELECT reaction FROM read_parquet('{BIG.as_posix()}') "
        f"OFFSET {off} LIMIT {n}").fetchall()
    total, aux_hits, stat, n_done = accumulate(rows, enum, verbose=False)
    payload = {
        "offset": off, "n": n, "n_done": n_done,
        "n_classified": sum(total.values()),
        "total": dict(total),
        "aux_hits": {k: dict(v) for k, v in aux_hits.items()},
        "stat": dict(stat),
        "seconds": round(time.time() - t0, 1),
    }
    Path(out_path).write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    # 单行摘要给总控解析（stdout 只留这一行 JSON，别混别的东西）
    print(json.dumps({"shard": out_path, "n_done": n_done,
                      "n_classified": sum(total.values()),
                      "seconds": payload["seconds"],
                      "stat": dict(stat)}, ensure_ascii=False), flush=True)
    return 0


def main():
    if len(sys.argv) >= 5 and sys.argv[1] == "--shard":
        return shard_main(int(sys.argv[2]), int(sys.argv[3]), sys.argv[4])
    cap = int(sys.argv[1]) if len(sys.argv) > 1 else 300000
    t0 = time.time()
    print("=" * 96)
    print(f"E-1 辅助试剂覆盖率（单进程版，最多 {cap:,} 条）")
    print("=" * 96)
    from smartreact import ReactionEnumerator
    enum = ReactionEnumerator()
    con = duckdb.connect()
    con.execute("SET memory_limit='1500MB'")
    con.execute("SET threads=2")
    rows = con.execute(
        f"SELECT reaction FROM read_parquet('{BIG.as_posix()}') LIMIT {cap}").fetchall()
    print(f"读入 {len(rows):,} 条反应，开始归类统计...", flush=True)
    total, aux_hits, stat, n_done = accumulate(rows, enum)
    print(f"\n跑完 {n_done:,} 条，归类成功 {sum(total.values()):,} 条，覆盖 {len(total)} 类")
    print("  失败/跳过原因（计数，不是静默）：")
    for k, v in stat.most_common(15):
        print(f"    {k:<24} {v:,}")
    summarize(total, aux_hits)
    print(f"  总耗时 {time.time()-t0:.0f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
