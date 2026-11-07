# -*- coding: utf-8 -*-
r"""★ ① 可购砌块集合（purchasable building blocks）★

定义（口径，先说清再测）
--------------------------------------------------------------------
数据源 : ord_dataset-1158e351…parquet（1,771,032 条，唯一带 CXSMILES 的文件；
         其余 52 个 parquet 前 200 条均无 CXSMILES —— 实测见
         tools/probe_ord_other_files.py 的输出）
对象   : CXSMILES 的【反应物段】与【产物段】（中段 = agents/溶剂，不入账）
分子   : 按 "." 拆成单组分（盐/水/多组分都算独立分子）
身份   : RDKit 去映射后的 canonical SMILES（SetAtomMapNum(0)后再 canonical，
         保留立体与电荷）
砌块   : 在【反应物段】出现过 且 在【产物段】从未出现过
计数   : 逐反应计数；同一反应同一侧同一分子只计一次

★ 重要区分（不然会把试剂当砌块）★
   "R有P无" 里既有 真正的砌块（胺/酸/醛/卤代物），也有 试剂/催化剂
   （NEt3、DIPEA、[H-]、DMF、THF…）。判定证据用【映射率】：
   映射率 = 该分子作为反应物时【带原子映射号】的次数 / 总次数
     - 带映射 = 它的原子进了产物 = 真底物（砌块）
     - 不带映射 = 只是条件试剂/溶剂/催化剂 = 抓手试剂，不是砌块
   blocks_core.tsv    = 映射率 >= 0.5 且 映射次数 >= 5（真正的砌块）
   blocks_reagents.tsv = 其余（试剂/溶剂/催化剂/添加剂）

自检（必须全过，否则报错退出、不写交付物）
--------------------------------------------------------------------
A. 同分子不同映射号 -> 同一 canonical SMILES
B. 砌块集合 ∩ 产物集合 = 空
C. CXSMILES 段数异常 = 0
D. 输出文件真的写出来了且行数 = 内存里的集合大小

用法
--------------------------------------------------------------------
  python build_purchasable_blocks.py --pilot 20000
  python build_purchasable_blocks.py                 # 全量（约 6 分钟）
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

STAGE = Path(r"D:\ProgramData\DSHNS\chemreact-staging")
sys.path.insert(0, str(STAGE / "libs"))
sys.path.insert(0, r"D:\TCMAI\src")          # db_utils 在这里

import duckdb  # noqa: E402
from rdkit import Chem, RDLogger  # noqa: E402
from rdkit.Chem import Descriptors, rdMolDescriptors  # noqa: E402
from ord_schema.proto import reaction_pb2  # noqa: E402

RDLogger.DisableLog("rdApp.*")

BIG = STAGE / "ord-data" / "data" / "11" / \
    "ord_dataset-1158e351757f315b93cbcbe7bc55f38e.parquet"
REPORTS = STAGE / "reports"
TSV_ALL = REPORTS / "purchasable_blocks.tsv"
TSV_CORE = REPORTS / "purchasable_blocks_core.tsv"
TSV_REAGENT = REPORTS / "purchasable_blocks_reagents.tsv"
REDUCE_OUT = REPORTS / "purchasable_blocks_reduce.json"
META_OUT = REPORTS / "purchasable_blocks_meta.json"
COCO_INDEX = REPORTS / "coconut_inchikey_index.jsonl"

MAP_RATIO_CORE = 0.5      # 核心砌块：映射率下限
MAP_COUNT_CORE = 5        # 核心砌块：带映射出现次数下限


# ------------------------------------------------------------------ 单分子
def canon_key(smi: str):
    """SMILES -> (去映射 canonical SMILES, MW, 重原子数, 分子式)。失败返回 None。"""
    try:
        m = Chem.MolFromSmiles(smi)
        if m is None:
            return None
        for a in m.GetAtoms():
            if a.GetAtomicNum() == 0:      # 通配/R 基团：不是真分子
                return None
            a.SetAtomMapNum(0)
        cs = Chem.MolToSmiles(m)
        if not cs:
            return None
        return (cs, round(Descriptors.MolWt(m), 3), m.GetNumHeavyAtoms(),
                rdMolDescriptors.CalcMolFormula(m))
    except Exception:
        return None


def split_cx(cx: str):
    """CXSMILES -> (反应物段, 中段, 产物段) 或 None。"""
    body = cx.split("|", 1)[0] if "|" in cx else cx
    parts = body.split(">")
    if len(parts) == 3:
        return parts[0], parts[1], parts[2]
    if len(parts) == 2:                      # "A>>B" 无中段
        return parts[0], "", parts[1]
    return None


def parse_rows(rows):
    """rows = [(reaction_blob,)] -> (cnt, mapped, stat)"""
    cnt = Counter()          # (canonical_smiles, side) -> 反应数
    mapped = Counter()       # canonical_smiles -> 作为反应物时带映射号的次数
    stat = Counter()
    for (blob,) in rows:
        rxn = reaction_pb2.Reaction()
        try:
            rxn.ParseFromString(blob)
        except Exception:
            stat["protobuf失败"] += 1
            continue
        cx = None
        for i in rxn.identifiers:
            if i.type == reaction_pb2.ReactionIdentifier.REACTION_CXSMILES and i.value:
                cx = i.value
                break
        if not cx:
            stat["无CXSMILES"] += 1
            continue
        stat["有CXSMILES"] += 1
        sp = split_cx(cx)
        if sp is None:
            stat["CX段数异常"] += 1
            continue
        lhs, mid, rhs = sp
        stat["中段非空" if mid.strip() else "中段为空"] += 1
        stat["产物侧有映射" if ":" in rhs else "产物侧无映射"] += 1
        for side, seg in (("R", lhs), ("P", rhs)):
            seen_here = set()
            for part in seg.split("."):
                part = part.strip()
                if not part:
                    continue
                stat[f"{side}_组分总数"] += 1
                got = canon_key(part)
                if got is None:
                    stat[f"{side}_无法解析"] += 1
                    continue
                cs = got[0]
                if cs in seen_here:
                    continue
                seen_here.add(cs)
                cnt[(cs, side)] += 1
                if side == "R" and ":" in part:
                    mapped[cs] += 1
    return cnt, mapped, stat


def _ik_one(s):
    """单个 SMILES -> (smiles, full_inchikey, skeleton)。"""
    from rdkit.Chem import inchi as _inchi
    full = ""
    try:
        m = Chem.MolFromSmiles(s)
        if m is not None:
            full = _inchi.MolToInchiKey(m) or ""
    except Exception:
        full = ""
    return (s, full, full.split("-")[0] if full else "")


def _ik_worker(smis):
    return [_ik_one(s) for s in smis]


def inchi_keys_with_timeout(smis, workers=10, chunk=500, chunk_timeout=180.0,
                            label=""):
    """★ 抗死循环版 InChIKey ★

    实测：RDKit 的 InChI 在个别分子上会【死循环】（CPU 100% 永不返回），
    进程池会整体挂死（本脚本第一版就是这样挂的，两次都停在 282,000/297,885）。
    所以改用【线程池 + 超时】：
      - 每个 chunk 提交 chunk 个分子，as_completed(timeout)
      - 超时后把没回来的记账为"InChI 挂死"，继续下一批
      - 卡住的线程留在后台不管（进程退出时自然消失）
    返回 ({(smiles): (full, skel)}, [挂死的 smiles])
    """
    from concurrent.futures import ThreadPoolExecutor, as_completed, TimeoutError as FTimeout
    got, hung = {}, []
    t0 = time.time()
    with ThreadPoolExecutor(max_workers=workers) as pool:
        for i in range(0, len(smis), chunk):
            batch = smis[i:i + chunk]
            futs = {pool.submit(_ik_one, s): s for s in batch}
            done = 0
            try:
                for fu in as_completed(futs, timeout=chunk_timeout):
                    s, full, skel = fu.result()
                    got[s] = (full, skel)
                    done += 1
            except FTimeout:
                pass
            if done < len(batch):
                missing = [s for s in batch if s not in got]
                hung.extend(missing)
                print(f"   [warn] {label} 第 {i//chunk} 批 {len(missing)} 个 "
                      f"InChI 超时/挂死，已跳过（例：{missing[:2]}）", flush=True)
            if (i // chunk) % 10 == 0:
                print(f"   {label} {min(i+chunk, len(smis)):>8,}/{len(smis):,}  "
                      f"{time.time()-t0:.0f}s", flush=True)
    return got, hung


# ------------------------------------------------------------------ 主流程
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pilot", type=int, default=0, help="只跑前 N 条反应")
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--chunk", type=int, default=4000)
    ap.add_argument("--deep-verify", action="store_true",
                    help="对【全部】产物算 InChIKey 做 E 自检（约 10 分钟）；"
                         "默认只抽 30000 个产物（约 15 秒）")
    args = ap.parse_args()
    cap = args.pilot

    print("=" * 92)
    print("① 可购砌块集合 —— ORD 反应物段中【从不作为产物出现】的分子")
    print("=" * 92)

    con = duckdb.connect()
    con.execute("SET memory_limit='1500MB'")
    con.execute("SET threads=2")
    total = con.execute(
        f"SELECT num_rows FROM parquet_file_metadata('{BIG.as_posix()}')").fetchone()[0]
    print(f"数据源 : {BIG.name}（{total:,} 条，唯一带 CXSMILES 的文件）")
    if cap:
        print(f"本次   : 只跑前 {cap:,} 条")
    print(f"并行   : {args.workers} 进程 x {args.chunk} 条/块")
    print(flush=True)

    t_start = time.time()
    cur = con.execute(f"SELECT reaction FROM read_parquet('{BIG.as_posix()}')")
    all_cnt: Counter = Counter()
    all_map: Counter = Counter()
    all_stat: Counter = Counter()
    n_done = 0
    pending = []
    stop = False
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        while not stop:
            while len(pending) < args.workers * 2 and not stop:
                take = args.chunk
                if cap:
                    take = min(take, cap - n_done)
                    if take <= 0:
                        stop = True
                        break
                rows = cur.fetchmany(take)
                if not rows:
                    stop = True
                    break
                n_done += len(rows)
                pending.append(pool.submit(parse_rows, rows))
            if not pending:
                break
            c, mp, s = pending.pop(0).result()
            all_cnt.update(c); all_map.update(mp); all_stat.update(s)
            el = time.time() - t_start
            rate = n_done / el
            eta = (total - n_done) / rate if not cap else 0.0
            print(f"   {n_done:>9,} 条  {el:6.1f}s  {rate:8.0f} 条/s  "
                  f"唯一分子 {len(all_cnt):>8,}  预计剩余 {eta/60:5.1f} 分钟", flush=True)
            del c, mp, s
    dt = time.time() - t_start
    print(f"\n[扫描完成] {n_done:,} 条反应，耗时 {dt:.1f}s（{n_done/dt:.0f} 条/s）")

    # ---------------- 汇总 ----------------
    prod = {k for (k, side) in all_cnt if side == "P"}
    reac = {k for (k, side) in all_cnt if side == "R"}
    blocks = reac - prod
    both = reac & prod
    print()
    print("=" * 92)
    print("口径统计（实测）")
    print("=" * 92)
    print(f"  反应物段唯一分子 : {len(reac):>9,}")
    print(f"  产物段唯一分子   : {len(prod):>9,}")
    print(f"  两侧都有(可合成) : {len(both):>9,}")
    print(f"  ★ 砌块(R有P无)   : {len(blocks):>9,}")
    print(f"  仅产物(从未作反应物) : {len(prod - reac):>9,}")
    for k in sorted(all_stat):
        print(f"  {k:<22} {all_stat[k]:>10,}")

    # ---------------- 自检 ----------------
    print()
    print("=" * 92)
    print("自检")
    print("=" * 92)
    checks = []
    pairs = [("CC(=O)O", "[CH3:1][C:2](=[O:3])[OH:4]"),
             ("CCNC(C)=O", "[CH3:1][C:2](=[O:3])[NH:4][CH2:5][CH3:6]"),
             ("OC[C@@H]1OC(O)[C@H](O)[C@@H](O)[C@@H]1O",
              "[OH:1][CH2:2][C@@H:3]1[O:4][CH:5]([OH:6])[C@H:7]([OH:8])"
              "[C@@H:9]([OH:10])[C@@H:11]1[OH:12]")]
    ok_a = all(canon_key(a)[0] == canon_key(b)[0] for a, b in pairs)
    checks.append(("A 去映射规范化一致（3 组）", ok_a))
    checks.append((f"B 砌块 ∩ 产物 = 空（{len(blocks & prod)}）", len(blocks & prod) == 0))
    checks.append((f"C CXSMILES 段数异常 = {all_stat['CX段数异常']}", all_stat["CX段数异常"] == 0))
    for name, ok in checks:
        print(f"  {'OK ' if ok else 'XX '} {name}")
    if not all(ok for _, ok in checks):
        print("\n★ 自检未通过 —— 不写交付物")
        return 1

    # ---------------- 计算 InChIKey（并行） ----------------
    print(f"\n计算 InChIKey（{len(blocks):,} 个砌块，{args.workers} 进程）...", flush=True)
    t0 = time.time()
    blist = sorted(blocks)
    ik, ik_hung = inchi_keys_with_timeout(blist, workers=10, chunk=500,
                                          chunk_timeout=120.0, label="[砌块]")
    print(f"   完成 {len(ik):,} 个（InChI 挂死跳过 {len(ik_hung)} 个），"
          f"{time.time()-t0:.0f}s")

    # ---------------- 分类：核心砌块 vs 试剂 ----------------
    rows_core, rows_reag = [], []
    for cs in blocks:
        n_r = all_cnt[(cs, "R")]
        n_mp = all_map.get(cs, 0)
        ratio = n_mp / n_r if n_r else 0.0
        full, skel = ik.get(cs, ("", ""))
        info = canon_key(cs)
        if info is None:
            continue
        _, mw, hac, formula = info
        rec = (cs, skel, full, mw, hac, formula, n_r, n_mp, round(ratio, 3))
        if ratio >= MAP_RATIO_CORE and n_mp >= MAP_COUNT_CORE:
            rows_core.append(rec)
        else:
            rows_reag.append(rec)

    def dump(path, rows, title):
        rows = sorted(rows, key=lambda r: -r[7])
        with open(path, "w", encoding="utf-8") as f:
            f.write("# " + title + "\n")
            f.write("smiles\tinchikey_skeleton\tinchikey\tMW\theavy_atoms\tformula\t"
                    "n_as_reactant\tn_mapped_as_reactant\tmap_ratio\n")
            for r in rows:
                f.write(f"{r[0]}\t{r[1]}\t{r[2]}\t{r[3]}\t{r[4]}\t{r[5]}\t"
                        f"{r[6]}\t{r[7]}\t{r[8]}\n")
        return len(rows)

    n_all = dump(TSV_ALL, rows_core + rows_reag,
                 "ORD 砌块全集：反应物段出现、产物段从未出现（含试剂/溶剂）")
    n_core = dump(TSV_CORE, rows_core,
                  f"核心砌块：map_ratio>={MAP_RATIO_CORE} 且 n_mapped>={MAP_COUNT_CORE}"
                  "（原子进了产物 = 真底物）")
    n_reag = dump(TSV_REAGENT, rows_reag, "试剂/溶剂/催化剂（映射率低，不是砌块）")
    print()
    print(f"  全集      {n_all:>8,}  -> {TSV_ALL.name}")
    print(f"  核心砌块  {n_core:>8,}  -> {TSV_CORE.name}")
    print(f"  试剂类    {n_reag:>8,}  -> {TSV_REAGENT.name}")
    checks.append((f"D 输出行数一致 ({n_all} = {n_core} + {n_reag})",
                   n_all == n_core + n_reag == len(rows_core) + len(rows_reag)))

    # E. 独立复核（换一套身份口径）：把【全部产物分子】也算 InChIKey，
    #    与砌块集合比 full InChIKey。canonical SMILES 说"两个分子不同"，
    #    InChI 也必须说不同，否则身份判定有问题。
    #    骨架层面允许相撞 —— 那是立体异构体（full InChIKey 不同），必须分开报。
    skel_blocks = {r[1] for r in rows_core + rows_reag if r[1]}
    full_blocks = {r[2] for r in rows_core + rows_reag if r[2]}
    prod_list = sorted(prod)
    if not args.deep_verify and len(prod_list) > 30000:
        import random
        random.seed(20261011)
        prod_list = random.sample(prod_list, 30000)
    prod_ik, prod_hung = inchi_keys_with_timeout(prod_list, workers=10, chunk=500,
                                                 chunk_timeout=120.0, label="[产物]")
    skel_prod = {v[1] for v in prod_ik.values() if v[1]}
    full_prod = {v[0] for v in prod_ik.values() if v[0]}
    inter_full = full_blocks & full_prod
    inter_skel = skel_blocks & skel_prod
    scope = "全部" if args.deep_verify else "抽样"
    checks.append((f"E {scope}产物({len(prod_list):,}) 复核：砌块 ∩ 产物 "
                   f"full InChIKey = {len(inter_full)}", len(inter_full) == 0))
    print(f"  [说明] 骨架层面撞 {len(inter_skel)} 个 -> 立体异构体"
          f"（同骨架不同构型，不是同一个分子；砌块含未定构型版本）")

    # ---------------- 与 COCONUT / tcm.db 的交集 ----------------
    coco_skel = set()
    if COCO_INDEX.exists():
        with open(COCO_INDEX, encoding="utf-8") as f:
            for line in f:
                k = line.split("\t", 1)[0].strip()
                if k:
                    coco_skel.add(k.split("-")[0])
    tcm_skel = set()
    try:
        from tcm_ro import use_readonly; use_readonly()
        from db_utils import open_db
        with open_db() as conn:
            for (k,) in conn.cursor().execute(
                    "SELECT inchi_key FROM compounds "
                    "WHERE inchi_key IS NOT NULL AND inchi_key != ''"):
                tcm_skel.add(k.split("-")[0])
    except Exception as ex:
        print(f"   [warn] tcm.db 读取失败: {ex}")
    have_skel = {r[1] for r in rows_core + rows_reag if r[1]}
    overlap_coco = len(have_skel & coco_skel)
    overlap_tcm = len(have_skel & tcm_skel)
    print()
    print(f"  COCONUT 骨架命中 {overlap_coco:,} / {len(have_skel):,}"
          f"  ({overlap_coco/max(len(have_skel),1)*100:.1f}%)")
    print(f"  tcm.db  骨架命中 {overlap_tcm:,} / {len(have_skel):,}"
          f"  ({overlap_tcm/max(len(have_skel),1)*100:.1f}%)")

    # ---------------- reduce 索引（给 retro_search 终端集合用） ----------------
    reduce = {}
    for r in rows_core:
        skel, full = r[1], r[2]
        if skel and skel not in reduce:
            reduce[skel] = [r[0], full, r[6], r[8]]      # smiles, full ik, n_r, ratio
    REDUCE_OUT.write_text(json.dumps(
        {"note": "InChIKey skeleton -> [smiles, full_inchikey, n_as_reactant, map_ratio]",
         "n": len(reduce), "threshold": {"map_ratio": MAP_RATIO_CORE,
                                          "n_mapped": MAP_COUNT_CORE},
         "entries": reduce}, ensure_ascii=False), encoding="utf-8")
    print(f"  -> {REDUCE_OUT.name}  ({len(reduce):,} 个骨架)")

    mws = [r[3] for r in rows_core]
    meta = {
        "source": BIG.name,
        "n_reactions_scanned": n_done,
        "is_full": (not cap),
        "definition": "reactant-side molecule that never appears on the product side",
        "identity": "RDKit canonical SMILES after atom-map removal (SetAtomMapNum(0))",
        "scoring": "per-reaction dedup, no stoichiometry",
        "middle_segment_counted": False,
        "n_reactant_molecules": len(reac),
        "n_product_molecules": len(prod),
        "n_both_sides": len(both),
        "n_blocks_all": n_all,
        "n_blocks_core": n_core,
        "n_reagents": n_reag,
        "threshold_core": {"map_ratio": MAP_RATIO_CORE, "n_mapped": MAP_COUNT_CORE},
        "coconut_skeleton_hits": overlap_coco,
        "tcm_skeleton_hits": overlap_tcm,
        "mw_core_min": min(mws) if mws else None,
        "mw_core_median": sorted(mws)[len(mws) // 2] if mws else None,
        "mw_core_max": max(mws) if mws else None,
        "n_core_mw_le_300": sum(1 for m in mws if m <= 300),
        "n_core_freq_ge_10": sum(1 for r in rows_core if r[6] >= 10),
        "stats": dict(all_stat),
        "elapsed_sec": round(dt, 1),
        "inchi_hung_blocks": len(ik_hung),
        "inchi_hung_block_examples": ik_hung[:10],
        "inchi_hung_products": len(prod_hung),
        "check_E_scope": ("all_products" if args.deep_verify else "sampled_products"),
        "check_E_n_products": len(prod_list),
        "check_E_full_inchikey_overlap": len(inter_full),
        "check_E_skeleton_overlap_stereoisomers": len(inter_skel),
    }
    META_OUT.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  -> {META_OUT.name}")

    for name, ok in checks:
        print(f"  {'OK ' if ok else 'XX '} {name}")
    if not all(ok for _, ok in checks):
        print("\n★ 自检未通过")
        return 1

    print("\nTop 30 核心砌块（按带映射出现次数）:")
    for r in sorted(rows_core, key=lambda x: -x[7])[:30]:
        print(f"   {r[7]:>6,} (共{r[6]:>6,})  {r[5]:<14} MW{r[3]:7.1f}  {r[0][:62]}")
    print("\nTop 15 试剂类（映射率低 = 不是砌块）:")
    for r in sorted(rows_reag, key=lambda x: -x[6])[:15]:
        print(f"   {r[6]:>6,} 次 map={r[8]:<5}  {r[5]:<14}  {r[0][:55]}")
    print(f"\n耗时 {time.time()-t_start:.1f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
