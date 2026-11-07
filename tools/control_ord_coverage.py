# -*- coding: utf-8 -*-
r"""★ 对照实验：修正上一轮分析里的三个偏差 ★

上一轮说"未命中 64.6%，其中 70.5% 是 A 类（模板完全没匹配上）"。
但那个数字可能虚高，因为：

  ① ORD 数据脏：有些记录的产物和底物根本对不上
     （例：底物无叔丁基，产物却是二叔丁基联苯）
     -> 用【元素守恒】剔除：产物任一元素数 > 全部输入该元素数之和 即为脏记录
  ② ORD 有重复记录 -> 去重
  ③ ★我自己的漏洞★：只取了 role=REACTANT。
     若偶联伙伴被标成 REAGENT（Suzuki 的硼酸常这样），
     我就误判成"模板没触发"。
     -> 对照：对全部"非溶剂"组分做任意两两配对，看能否复现

指标：
  M1 严格 = 只用 role=REACTANT（且恰 2 个）           <- 上一轮的口径
  M2 宽松 = 非溶剂组分任意两两配对中，有一对能复现     <- 更公平的口径
"""
import sys
import time
from collections import Counter
from pathlib import Path

STAGE = Path(r"D:\ProgramData\DSHNS\chemreact-staging")
sys.path.insert(0, str(STAGE / "libs"))

import duckdb  # noqa: E402
from rdkit import Chem, RDLogger  # noqa: E402
from ord_schema.proto import reaction_pb2  # noqa: E402
from smartreact import ReactionEnumerator  # noqa: E402

RDLogger.DisableLog("rdApp.*")

TARGET = int(sys.argv[1]) if len(sys.argv) > 1 else 1200

_rf = reaction_pb2.Compound.DESCRIPTOR.fields_by_name["reaction_role"]
_role_enum = _rf.enum_type
_ci = reaction_pb2.CompoundIdentifier


def role_name(n):
    v = _role_enum.values_by_number.get(n)
    return v.name if v else f"<{n}>"


def canon(smi):
    try:
        m = Chem.MolFromSmiles(smi)
        if m is None:
            return None
        for a in m.GetAtoms():
            a.SetAtomMapNum(0)
        return Chem.MolToSmiles(m)
    except Exception:
        return None


def elem_counts(smi):
    """加氢后的元素计数（含 H），用于元素守恒检查。"""
    try:
        m = Chem.MolFromSmiles(smi)
        if m is None:
            return None
        m = Chem.AddHs(m)
        c = Counter()
        for a in m.GetAtoms():
            c[a.GetSymbol()] += 1
        return c
    except Exception:
        return None


def smi_of(comp):
    v = next((x.value for x in comp.identifiers if x.type == _ci.SMILES), None)
    if v is None:
        v = next((x.value for x in comp.identifiers), None)
    return v


ORD = STAGE / "ord-data"
pq = sorted((ORD / "data").rglob("*.parquet"))
con = duckdb.connect()
con.execute("SET memory_limit='1500MB'")
con.execute("SET threads=2")

plan, total_rows = [], 0
for p in pq:
    try:
        n = con.execute(
            f"SELECT num_rows FROM parquet_file_metadata('{p.as_posix()}')").fetchone()[0]
    except Exception:
        n = 0
    plan.append((p, n))
    total_rows += n
quota = [(p, max(20, round(TARGET * n / total_rows))) for p, n in plan if n > 40]

enum = ReactionEnumerator()
stat = Counter()
seen_keys = set()
t0 = time.time()

for p, k in quota:
    try:
        rows = con.execute(
            f"SELECT reaction_id, reaction FROM read_parquet('{p.as_posix()}') "
            f"USING SAMPLE {k} ROWS").fetchall()
    except Exception:
        continue
    for rid, blob in rows:
        rxn = reaction_pb2.Reaction()
        try:
            rxn.ParseFromString(blob)
        except Exception:
            stat["protobuf失败"] += 1
            continue

        # 全部输入组分（保留角色）
        all_comps = []      # (role, smiles)
        for key, inp in rxn.inputs.items():
            for c in inp.components:
                s = smi_of(c)
                if s:
                    all_comps.append((role_name(c.reaction_role), s))
        reactants = [s for r, s in all_comps if r == "REACTANT"]

        products = []
        for oc in rxn.outcomes:
            for pr in oc.products:
                s = smi_of(pr)
                if s:
                    products.append(s)
        if not products:
            stat["无产物(跳过)"] += 1
            continue

        exp = {canon(x) for x in products} - {None}
        if not exp:
            stat["产物非法(跳过)"] += 1
            continue

        # ---- ③ 去重 ----
        dkey = (canon(products[0]), tuple(sorted(canon(x) or x for x in reactants)))
        if dkey in seen_keys:
            stat["重复记录(去重)"] += 1
            continue
        seen_keys.add(dkey)

        # ---- ① 元素守恒：产物任一元素不能超过全部输入之和 ----
        pc = elem_counts(products[0])
        ic = Counter()
        ok_counts = True
        for _, s in all_comps:
            c = elem_counts(s)
            if c is None:
                ok_counts = False
                break
            ic += c
        if pc is None or not ok_counts:
            stat["元素无法计算(跳过)"] += 1
            continue
        bad = [e for e, n in pc.items() if n > ic.get(e, 0)]
        if bad:
            stat["★脏记录(元素守恒违反)"] += 1
            continue

        # ---- M1: 严格口径 ----
        if len(reactants) != 2:
            stat[f"底物数={len(reactants)}(M1不可测)"] += 1
            m1_testable = False
        else:
            m1_testable = True
            stat["M1 可测"] += 1

        # ---- 主判定 ----
        hit_m1 = False
        if m1_testable:
            try:
                res = enum.enumerate_pair(reactants[0], reactants[1])
                got = {canon(pr) for r in res for pr in r.products} - {None}
                hit_m1 = bool(got & exp)
            except Exception:
                stat["枚举异常"] += 1
        if hit_m1:
            stat["M1 命中"] += 1

        # ---- M2: 宽松口径（非溶剂任意两两）+ 顺便给 M1 兜底 ----
        pool = sorted({s for r, s in all_comps if r not in ("SOLVENT",)})
        hit_m2 = hit_m1
        if not hit_m2 and len(pool) >= 2:
            tried = 0
            for i in range(len(pool)):
                if hit_m2:
                    break
                for j in range(i + 1, len(pool)):
                    if tried >= 25:
                        break
                    tried += 1
                    try:
                        res = enum.enumerate_pair(pool[i], pool[j])
                        got = {canon(pr) for r in res for pr in r.products} - {None}
                        if got & exp:
                            hit_m2 = True
                            break
                    except Exception:
                        continue
            if hit_m2 and not hit_m1:
                stat["★M2 额外救回（M1 取法漏了）"] += 1
        if hit_m2:
            stat["M2 命中"] += 1
            if m1_testable:
                stat["M2 在M1子集内命中"] += 1
            else:
                stat["M2 在M1不可测集内命中"] += 1
        if len(pool) >= 2:
            stat["可用于M2的反应"] += 1

        if (stat["M1 可测"] + stat["M2 命中"]) % 300 == 0:
            print(f"  ... 已处理，耗时 {time.time()-t0:.0f}s", flush=True)

print(f"\n处理完成，耗时 {time.time()-t0:.1f}s\n")

# ---------------- 报告 ----------------
m1t = stat["M1 可测"]
m1h = stat["M1 命中"]
m2h = stat["M2 命中"]
print("=" * 92)
print("数据质量清理结果")
print("=" * 92)
for k in ("protobuf失败", "无产物(跳过)", "产物非法(跳过)", "重复记录(去重)",
          "元素无法计算(跳过)", "★脏记录(元素守恒违反)"):
    print(f"   {k:<28} {stat[k]}")

print()
print("=" * 92)
print("★ 覆盖率对照（分母严格对齐，同一条反应上比 M1 vs M2）")
print("=" * 92)
m2_all = stat["可用于M2的反应"]
m2_in_m1 = stat["M2 在M1子集内命中"]
print(f"  【口径 M1】只用 role=REACTANT 且恰 2 个")
print(f"      可测 {m1t}   命中 {m1h}   -> {m1h/m1t*100:.1f}%" if m1t else "      无可测")
print()
print(f"  【口径 M2】非溶剂组分任意两两配对（最多试 25 对）")
print(f"      可测 {m2_all}   命中 {stat['M2 命中']}   -> "
      f"{stat['M2 命中']/m2_all*100:.1f}%" if m2_all else "      无可测")
print()
print(f"  ★ 同一条反应上直接对比（M1 可测的那 {m1t} 条）：")
print(f"      M1 命中 {m1h}  ({m1h/m1t*100:.1f}%)" if m1t else "")
print(f"      M2 命中 {m2_in_m1}  ({m2_in_m1/m1t*100:.1f}%)" if m1t else "")
print(f"      -> M2 多救回 {stat['★M2 额外救回（M1 取法漏了）']} 条，"
      f"这些是【我的取法漏的】，不是规则库缺口")
print()
print(f"      另有 {stat['M2 在M1不可测集内命中']} 条反应，"
      f"M1 因底物数≠2 根本测不了，但 M2 能复现")
print()
print("  注：M2 每条约只试 25 对，所以 M2 是【下界】，真实值只会更高。")

print()
print("  M1 不可测的原因分布:")
for k, v in stat.most_common(30):
    if "M1不可测" in k:
        print(f"      {k:<34} {v}")

enum.close()
con.close()
