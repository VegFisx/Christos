# -*- coding: utf-8 -*-
r"""跑反应级验收测试集。

判据：
  · kind="rule"    指定规则作用在指定底物上，产物必须包含 expect_any 里的某个分子，
                   且不得包含 forbid 里的任何分子
  · kind="gating"  指定条件下，某类别/某规则必须激活或必须熄灭

★ 失败不是坏事——它暴露的是「我以为的」和「引擎实际做的」之间的差距。
  用例写错和引擎错，两种都要查清楚是哪一种。
"""
import json
import sys
from collections import Counter
from pathlib import Path

STAGE = Path(r"D:\ProgramData\DSHNS\chemreact-staging")
for d in ("core", "conditions", "rules", "libs", "sources"):
    p = STAGE / d
    if p.is_dir():
        sys.path.insert(0, str(p))

from rdkit import Chem, RDLogger
RDLogger.DisableLog("rdApp.error")
RDLogger.DisableLog("rdApp.warning")

# ★ 第七十五轮 H3：用例里的分子改成**从 tcm.db 取**（InChIKey 引用）。
#   本模块只读库（tools\case_db.py → tcm_ro.open_db 的 mode=ro），找不到就报错。
sys.path.insert(0, str(Path(__file__).resolve().parent))
import case_db

from engine import Compound, load_engine
import templates as T
from activator import active_rules

engine, rules, profiles = load_engine()
by_id = {r["id"]: r for r in rules}

def _load_cases():
    """把两批用例合起来读。"""
    out = []
    for name in ("reaction_cases.json", "reaction_cases2.json"):
        p = STAGE / "tools" / name
        if p.exists():
            out.extend(json.loads(p.read_text(encoding="utf-8")))
    return out


CASES = _load_cases()


def canon(smi):
    m = Chem.MolFromSmiles(smi)
    return Chem.MolToSmiles(m) if m else None


def mol_of(ref):
    """用例里的分子字段 → SMILES。dict=数据库引用（查不到就抛错）/ str=库外字面量。"""
    return case_db.resolve(ref)


def src_of(ref):
    return "库" if (isinstance(ref, dict) and ref.get("db")) else "字面量"


def run_rule_case(c: dict):
    """返回 (通过?, 说明)"""
    r = by_id.get(c["rule"])
    if r is None:
        return False, f"规则不存在: {c['rule']}"
    smi = mol_of(c["smiles"])
    mol = Chem.MolFromSmiles(smi)
    if mol is None:
        return False, f"底物 SMILES 解析失败: {smi}"

    cond = T.get_template(c.get("conditions") or "煎煮")
    act = {rr["id"]: s for rr, s, _ in active_rules(rules, profiles, cond)}
    score = act.get(c["rule"])
    if score is None:
        return False, f"规则在「{c.get('conditions')}」下未激活（用例条件可能选错）"

    sub = Compound(smiles=smi, name=c["name"], herb="test")
    prods = engine.apply_rule(r, sub, score, 1, cond)
    got = {canon(p.smiles) for p in prods if p.smiles}
    got.discard(None)

    want = {canon(mol_of(s)) for s in c.get("expect_any") or []}
    want.discard(None)
    forbid = {canon(mol_of(s)) for s in c.get("forbid") or []}
    forbid.discard(None)

    if forbid & got:
        bad = forbid & got
        return False, f"出现了不该有的产物: {sorted(bad)[:2]}"

    if want and not (want & got):
        return False, (f"未产出期望产物。期望其一 {sorted(want)[:2]}；"
                       f"实际产出 {len(got)} 个: {sorted(got)[:3]}")

    return True, f"产出 {len(got)} 个，命中期望"


def run_gating_case(c: dict):
    cond = T.get_template(c["conditions"])
    act = {rr["id"] for rr, _s, _w in active_rules(rules, profiles, cond)}

    for cat in c.get("must_inactive_categories") or []:
        hit = {r["id"] for r in rules
               if r.get("category") == cat and r.get("status") != "disabled"}
        bad = hit & act
        if bad:
            return False, f"类别 {cat} 下不应激活，却激活了: {sorted(bad)[:3]}"

    for cat in c.get("must_active_categories") or []:
        hit = {r["id"] for r in rules
               if r.get("category") == cat and r.get("status") != "disabled"}
        missing = hit - act
        if missing:
            return False, f"类别 {cat} 下应激活，却熄灭了: {sorted(missing)[:3]}"

    for rid in c.get("must_active_rules") or []:
        if rid not in act:
            return False, f"规则 {rid} 应当激活，实际未激活"

    for rid in c.get("must_inactive_rules") or []:
        if rid in act:
            return False, f"规则 {rid} 应当熄灭，实际激活"

    return True, f"激活 {len(act)} 条，门控符合预期"


PASS, FAIL = [], []
print("=" * 96)
print(f"{'用例':<30}{'规则':<34}{'结果'}")
print("-" * 96)

for c in CASES:
    kind = c.get("kind", "rule")
    if kind == "gating":
        ok, why = run_gating_case(c)
        label = c["conditions"]
    else:
        ok, why = run_rule_case(c)
        label = c.get("rule", "")

    if ok:
        PASS.append(c["id"])
    else:
        FAIL.append((c, why))

    mark = "✓" if ok else "✗"
    # ★ H3：每条用例标出**分子来源**（数据库 / 库外字面量），不隐藏任何一条
    _src = "-"
    if kind != "gating" and c.get("smiles"):
        if isinstance(c["smiles"], dict) and c["smiles"].get("db"):
            _src = "库:%s" % case_db.by_key(c["smiles"]["db"])[0][:18]
        else:
            _src = "字面量:%s" % mol_of(c["smiles"])[:18]
    print(f"{mark} {c['id']:<28}{label:<34}{_src:<26}{why if ok else ''}")
    if not ok:
        print(f"    ★ {why}")
        if c.get("note"):
            print(f"      依据: {c['note']}")

print()
print("=" * 96)
print(f"结果：{len(PASS)} 通过 / {len(FAIL)} 失败  （共 {len(CASES)} 条）")
print("=" * 96)

if FAIL:
    print("\n失败清单：")
    for c, why in FAIL:
        print(f"  ✗ {c['id']}")
        print(f"      {why}")

by_kind = Counter(c.get("kind", "rule") for c in CASES)
print(f"\n按类型：{dict(by_kind)}")
covered = {c["rule"] for c in CASES if c.get("rule")}
active_ids = {r["id"] for r in rules if r.get("status") != "disabled"}
missing = sorted(active_ids - covered)
print(f"覆盖规则 {len(covered & active_ids)} / {len(active_ids)} 条【启用】规则"
      f"（另有 {len(rules) - len(active_ids)} 条已停用）")

# ★ 作为防线：启用规则必须 100% 有用例 ★
#   起因：第 25 轮补「对位醌」两条规则时，加了规则却没加用例，
#   于是「覆盖 56/63」这个数字挂了十几轮都没人注意 —— 那两条规则
#   从没被任何已知答案验证过，只在临时脚本里验过一次。
if missing:
    print()
    print(f"  ★ 有 {len(missing)} 条启用规则【没有验收用例】：")
    for rid in missing:
        nm = next((r["name"] for r in rules if r["id"] == rid), "?")
        print(f"      {nm}  ({rid})")
    print("  → 新增规则必须同时加用例，否则这里是红的")
    raise SystemExit(1)
print("  ✓ 全部启用规则都有验收用例")

