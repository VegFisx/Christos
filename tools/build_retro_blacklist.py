# -*- coding: utf-8 -*-
r"""D7（2026-10-14）：把逆模板体检的「never usable」模板固化成黑名单 + 前后对比。

输入 : reports/retro_template_audit.jsonl（tools/audit_retro_templates.py 的逐条体检结果）
判据 : n_try >= 5 且 n_usable == 0（写死：≥5 次切断、从没产出过可用路线）
       ★ 第四十二轮增补：另把 reports/template_identity_audit.json 里的【全等 no-op】模板
       （同一分子原样出现在反应两边；只会把目标自己当前体还回来）并入同一份黑名单
       （noop_entries，kind="noop"；生成用 tools/audit_template_identity.py）
输出 : reports/retro_template_blacklist.json
       主键 = smarts 字符串（不用 idx —— 模板库一旦重建，行号就不可靠）
       附「有/无黑名单」的前后对比（可用率 / 假路线数），全部从同一份体检 jsonl 聚合。

为什么默认关（开关落在使用方，不在本脚本）：黑名单是从 56 个目标样本上冻出来的经验结论，
不是化学定理 —— 换一批目标，某条模板可能又变可用。所以它只做**默认关**的开关：
打开只影响本次搜索，不改模板库文件（reports/retro_templates_clustered.jsonl 一个字不动）。

用法: python tools/build_retro_blacklist.py [体检jsonl路径]
       （缺省用 reports/retro_template_audit.jsonl —— 换输入路径 = 用新体检重新冻结）
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
AUDIT_JSONL = STAGE / "reports" / "retro_template_audit.jsonl"
AUDIT_SUMMARY = STAGE / "reports" / "retro_template_audit_summary.json"
IDENTITY_AUDIT = STAGE / "reports" / "template_identity_audit.json"
HOLDOUT_CHECK = STAGE / "reports" / "_holdout_blacklist_check.json"
R2_EXT = STAGE / "reports" / "paper" / "results" / "blacklist_ext_r2.json"
TEMPLATE_LIB = STAGE / "reports" / "retro_templates_clustered.jsonl"
OUT = STAGE / "reports" / "retro_template_blacklist.json"

# 判据写死（与 audit_retro_templates.py 的 bad 口径一致）
CRITERION_N_TRY = 5


def load_rows(path: Path):
    rows = []
    bad_lines = 0
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except Exception:
                bad_lines += 1
    return rows, bad_lines


def agg(rows):
    """按行聚合：try / usable / 各原因计数 + 可用率 + 假路线数（不可用总数）。"""
    tot = {}
    for r in rows:
        for k, v in r.items():
            if isinstance(v, int) and (k.startswith("n_") or (k.startswith("R") and k[1:2].isdigit())
                                       or k.startswith("run_")):
                tot[k] = tot.get(k, 0) + v
    tot["usable_rate"] = round(tot.get("n_usable", 0) / max(1, tot.get("n_try", 0)), 4)
    tot["n_unusable"] = tot.get("n_try", 0) - tot.get("n_usable", 0)
    tot["n_templates_with_hits"] = len(rows)
    return tot


def fmt_block(name, a):
    parts = [f"try {a.get('n_try', 0):,} · 可用 {a.get('n_usable', 0)} ({a['usable_rate']:.2%})"
             f" · 假路线 {a.get('n_unusable', 0):,}"]
    reasons = " / ".join(f"{k.split('_')[0]} {v:,}" for k, v in sorted(a.items())
                         if (k.startswith("R") and k[1:2].isdigit()) or k.startswith("run_"))
    if reasons:
        parts.append(f"（{reasons}）")
    return f"  {name:<7}: " + "".join(parts)


def main() -> int:
    t0 = time.time()
    audit_jsonl = Path(sys.argv[1]) if len(sys.argv) > 1 else AUDIT_JSONL
    is_default_src = (audit_jsonl == AUDIT_JSONL)

    def _rel(p):
        try:
            return str(Path(p).relative_to(STAGE))
        except Exception:
            return str(p)

    print("=" * 78)
    print("D7 黑名单生成：never-usable 逆模板 -> reports/retro_template_blacklist.json")
    print("=" * 78)
    if not audit_jsonl.exists():
        print(f"  [error] 找不到体检结果：{audit_jsonl}")
        print("          先跑 python tools/audit_retro_templates.py 56（约 272 s）")
        return 2

    rows, bad_lines = load_rows(audit_jsonl)
    if bad_lines:
        print(f"  [warn] 体检 jsonl 有 {bad_lines} 行解析失败（不静默，请检查）")

    bad = [r for r in rows if r.get("n_try", 0) >= CRITERION_N_TRY and r.get("n_usable", 0) == 0]
    weak = [r for r in rows if r.get("n_try", 0) < CRITERION_N_TRY and r.get("n_usable", 0) == 0]

    # ★ 第四十三轮（用户拍板 2026-10-14）：留出复测（COCONUT 64 个新目标）里**产出过可用**的
    #   条目 -> 从生效名单里移出（记入 exempted + 证据），不再当"never-usable"。
    holdout_ok = {}
    if HOLDOUT_CHECK.exists():
        try:
            hc = json.loads(HOLDOUT_CHECK.read_text(encoding="utf-8"))
            for r in hc.get("rows", []):
                if int(r.get("new_n_usable", 0) or 0) > 0:
                    holdout_ok[str(r.get("smarts", ""))] = {
                        "targets": hc.get("targets"), "n_try": r.get("new_n_try"),
                        "n_usable": r.get("new_n_usable")}
        except Exception as ex:                      # noqa: BLE001 —— 打印，不静默
            print(f"  [warn] 留出复测文件读取失败：{type(ex).__name__}: {ex}")
    else:
        print("  [warn] 未见 reports/_holdout_blacklist_check.json —— 本次不做留出豁免"
              "（名单 = 冻结判据原样；先跑 tools/_probe_holdout_blacklist.py）")
    exempt = [r for r in bad if str(r.get("smarts", "")) in holdout_ok]
    active = [r for r in bad if str(r.get("smarts", "")) not in holdout_ok]

    # ★ B8（2026-10-14）：第二批 —— "保护基/官能化添加"逆用族（全 R2、0 可用）并入，kind="r2_family"
    r2_entries, r2_missing = [], []
    if R2_EXT.exists():
        try:
            ext = json.loads(R2_EXT.read_text(encoding="utf-8"))
            for e in ext.get("entries", []):
                s = str(e.get("smarts") or "").strip()
                if not s:
                    continue
                r2_entries.append({
                    "smarts": s, "kind": "r2_family",
                    "n_cuts_sample": e.get("n_cuts"), "n_usable_sample": e.get("n_usable"),
                    "evidence": ("50k 抽样内全部切断为 R2（前体更大）且 0 可用；"
                                 "来源 reports/paper/results/blacklist_ext_r2.json")})
        except Exception as ex:                      # noqa: BLE001 —— 打印，不静默
            print(f"  [warn] B8 扩展读取失败：{type(ex).__name__}: {ex}")
    else:
        print("  [warn] 未见 reports/paper/results/blacklist_ext_r2.json —— R2 家族扩展暂缺"
              "（先跑 tools/paper_b8_ext.py）")

    bad_smarts = {str(r.get("smarts", "")) for r in bad}
    kept = [r for r in rows if str(r.get("smarts", "")) not in bad_smarts]
    before, after = agg(rows), agg(kept)

    # 校对：从 jsonl 重算的合计必须与体检汇总 json 一致（不一致 = 数据被改过，要喊出来）
    check = "（自定义输入源，跳过与汇总 json 的核对）"
    if is_default_src and AUDIT_SUMMARY.exists():
        summ = json.loads(AUDIT_SUMMARY.read_text(encoding="utf-8"))
        t = summ.get("totals", {})
        ok = (t.get("n_try") == before.get("n_try") and t.get("n_usable") == before.get("n_usable")
              and summ.get("n_never_usable_templates") == len(bad))
        check = (f"重算 n_try {before.get('n_try'):,} vs 汇总 {t.get('n_try', '?')}、"
                 f"n_usable {before.get('n_usable')} vs {t.get('n_usable', '?')}、"
                 f"never-usable {len(bad)} vs {summ.get('n_never_usable_templates', '?')}"
                 f" -> {'一致 OK' if ok else '★不一致，请查（数据可能被重跑改过）'}")
    elif is_default_src:
        check = "（汇总 json 缺失，跳过）"

    # 模板库核对：54 条 smarts 必须都能在库文件里找到（否则黑名单会失配、静默失效）
    lib_smarts, n_lib = set(), 0
    if TEMPLATE_LIB.exists():
        with open(TEMPLATE_LIB, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    lib_smarts.add(str(json.loads(line).get("template", "")))
                    n_lib += 1
                except Exception:
                    pass
    active_smarts = {str(r.get("smarts", "")) for r in active}
    missing = sorted(s for s in active_smarts if s and s not in lib_smarts)
    r2_missing = sorted(s for s in {e["smarts"] for e in r2_entries}
                        if s and s not in lib_smarts)

    # ★ 第四十二轮（质检员）：把"全等 no-op"也并入同一份黑名单
    noop_entries, noop_missing = [], []
    if IDENTITY_AUDIT.exists():
        try:
            ia = json.loads(IDENTITY_AUDIT.read_text(encoding="utf-8"))
            for x in ia.get("noop", []):
                if x.get("lib") != "retro" or not x.get("in_compiled"):
                    continue
                s = str(x.get("smarts") or "")
                if not s:
                    continue
                noop_entries.append({
                    "smarts": s, "kind": "noop", "line": x.get("line"),
                    "evidence": "同一分子原样出现在反应两边（映射号集合一致）；"
                                "只会把目标自己当前体还回来"})
                if s not in lib_smarts:
                    noop_missing.append(s)
        except Exception as ex:                      # noqa: BLE001 —— 打印，不静默
            print(f"  [warn] identity audit 读取失败：{type(ex).__name__}: {ex}")
    else:
        print("  [warn] 未见 reports/template_identity_audit.json —— no-op 条目暂缺"
              "（先跑 tools/audit_template_identity.py）")

    out = {
        "generated": time.strftime("%Y-%m-%d %H:%M:%S"),
        "source_audit_jsonl": _rel(audit_jsonl),
        "source_audit_summary": str(AUDIT_SUMMARY.relative_to(STAGE)),
        "criterion": f"n_try >= {CRITERION_N_TRY} 且 n_usable == 0",
        "criterion_note": ("来自 reports/retro_template_audit.jsonl 的实测（56 个目标 × 3,025 条逆模板；"
                           "口径见 tools/audit_retro_templates.py）"),
        "template_lib": str(TEMPLATE_LIB.relative_to(STAGE)),
        "verify_vs_lib": {"n_lib_rows": n_lib, "n_blacklist_in_lib": len(active) - len(missing),
                          "n_missing": len(missing), "missing_smarts": missing[:5],
                          "n_noop_missing": len(noop_missing)},
        "n_entries": len(active),
        "n_exempted": len(exempt),
        "exempt_note": ("留出复测（COCONUT 64 个新目标）里产出过可用切断 -> 移出 never-usable；"
                        "证据 reports/_holdout_blacklist_check.json（用户拍板 2026-10-14）"),
        "exempted": [{"smarts": str(r.get("smarts", "")), "idx": r.get("idx"),
                      "holdout": holdout_ok[str(r.get("smarts", ""))]} for r in exempt],
        "n_noop_entries": len(noop_entries),
        "noop_note": ("全等 no-op（同一分子原样两边穿过）——随同一开关丢弃；"
                      "来源 reports/template_identity_audit.json"),
        "n_weak_not_included": len(weak),
        "weak_note": ("n_try<5 且 n_usable==0 —— 证据不足，不入黑名单（下次体检样本扩大再看）"),
        "weak_idx_n_try": [{"idx": r["idx"], "n_try": r.get("n_try", 0)} for r in weak],
        "comparison_before_after": {
            "before": before, "after": after,
            "note": (f"前后对比 = 同一份体检数据里「用全部模板」vs「砍掉 never-usable {len(bad)} 条」；"
                     "after 的聚合 = 开关打开后搜索侧的等价效果（模板不再产出这些切断）"),
        },
        "check_vs_summary": check,
        "noop_entries": noop_entries,
        "n_r2_family_entries": len(r2_entries),
        "r2_family_note": ("第二批（B8）：保护基/官能化添加逆用族 —— 50k 抽样内全部切断为 R2 且 0 可用；"
                           "来源 reports/paper/results/blacklist_ext_r2.json"),
        "r2_family_entries": r2_entries,
        "entries": sorted(
            ({"smarts": str(r.get("smarts", "")), "idx": r.get("idx"),
              "n_try": r.get("n_try", 0), "n_usable": 0,
              "reasons": {k: v for k, v in r.items()
                          if isinstance(v, int) and ((k.startswith("R") and k[1:2].isdigit())
                                                     or k.startswith("run_"))}}
             for r in active),
            key=lambda e: e["idx"]),
    }
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")

    print(f"体检来源 : {audit_jsonl.name}（{len(rows)} 条有命中记录的模板）")
    print(f"判据     : n_try >= {CRITERION_N_TRY} 且 n_usable == 0 —— 冻结命中 {len(bad)} 条"
          f"；留出复测豁免 {len(exempt)} 条 -> 生效 {len(active)} 条")
    for r in exempt:
        h = holdout_ok[str(r.get("smarts", ""))]
        print(f"  ★ 豁免 idx {r.get('idx')}: 留出 {h['n_try']}/{h['n_usable']} 可用 -> 移出"
              f"（原体检 {r.get('n_try')} 次全部不可用）")
    print(f"证据不足 : {len(weak)} 条（n_try<5 且 n_usable==0，只记录不入黑名单）"
          f"  idx={[r['idx'] for r in weak]}")
    print(f"校对     : {check}")
    print("-" * 78)
    print(f"前后对比（同一批体检数据，只砍 never-usable {len(bad)} 条；no-op 条目不在这个对比里）：")
    print(fmt_block("before", before))
    print(fmt_block("after", after))
    d_try = before.get("n_try", 0) - after.get("n_try", 0)
    print(f"  砍掉   : try -{d_try:,}（-{d_try / max(1, before.get('n_try', 1)):.1%}）"
          f" · 假路线 -{before.get('n_unusable', 0) - after.get('n_unusable', 0):,}"
          f" · 可用 {before.get('n_usable', 0)} -> {after.get('n_usable', 0)}"
          f"（黑名单定义 = 0 产出，所以可用数期望不变）")
    print("-" * 78)
    if missing:
        print(f"★ 模板库核对：{len(active) - len(missing)}/{len(active)} 条在 {TEMPLATE_LIB.name} 里"
              f"，缺 {len(missing)} 条（模板库更新过？黑名单会对这些静默失配）")
    else:
        print(f"模板库核对：{len(active)}/{len(active)} 条 smarts 都在 {TEMPLATE_LIB.name}"
              f"（{n_lib} 行）✓")
    if noop_entries:
        if noop_missing:
            print(f"no-op 并入：{len(noop_entries) - len(noop_missing)}/{len(noop_entries)} 条在库里，"
                  f"缺 {len(noop_missing)} 条（要查）")
        else:
            print(f"no-op 并入：{len(noop_entries)} 条（全等模板；开关打开时一并丢弃）")
    if r2_entries:
        if r2_missing:
            print(f"R2 家族并入：{len(r2_entries) - len(r2_missing)}/{len(r2_entries)} 条在库里，"
                  f"缺 {len(r2_missing)} 条（要查）")
        else:
            print(f"R2 家族并入：{len(r2_entries)} 条（全 R2、0 可用；开关打开时一并丢弃）")
    print(f"黑名单合计：never-usable {len(active)}（另豁免 {len(exempt)}）+ R2 家族 "
          f"{len(r2_entries)} + no-op {len(noop_entries)} = "
          f"{len(active) + len(r2_entries) + len(noop_entries)} 条（开关打开时丢弃）")
    print(f"写出：{OUT}（{OUT.stat().st_size:,} 字节，{time.time() - t0:.1f}s）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
