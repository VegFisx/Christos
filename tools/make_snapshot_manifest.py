# -*- coding: utf-8 -*-
r"""快照：对关键文件生成 sha256 清单（论文/软著/版本一致性用）。

用法：``python tools\make_snapshot_manifest.py [版本号，默认 v1.0.0]``
"""
from __future__ import annotations

import hashlib
import sys
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

STAGE = Path(r"D:\ProgramData\DSHNS\chemreact-staging")
VERSION = sys.argv[1] if len(sys.argv) > 1 else "v1.0.0"
OUT = STAGE / "reports" / "release" / (
    "sha256_manifest.txt" if VERSION == "v1.0.0"
    else "sha256_manifest_%s.txt" % VERSION)

KEYS = [
    "reports/mined_forward_templates_full.jsonl",
    "reports/mined_forward_templates_full_lf.jsonl",
    "reports/retro_templates_freq10.jsonl",
    "reports/retro_template_blacklist.json",
    "reports/paper/data/lib_full_v2.jsonl",
    "reports/paper/data/lib_uspto50k_excl_v2.jsonl",
    "reports/paper/data/lib_uspto50k_excl_v2_freq10.jsonl",
    "reports/paper/data/uspto50k_canon.jsonl",
    "reports/chp_markers_2025/chp2025_curated.csv",
    "reports/chp_markers_2025/chp2025_linked.csv",
    "reports/chp_markers_2025/gold_check.json",
    "reports/paper/results/forward_50k.json",
    "reports/paper/results/forward_50k__full_s10_full50k.json",
    "reports/paper/results/forward_50k__cap32_20k_full50k.json",
    "reports/paper/results/forward_50k__lf_cap32_20k_full50k.json",
    "reports/paper/results/coverage_summary__lib_uspto50k_excl_v2_s10.json",
    "reports/paper/results/coverage_summary__lib_uspto50k_excl_v2_freq10_s10.json",
    "reports/paper/results/usability_summary__lib_uspto50k_excl_v2_c100.json",
    "reports/paper/results/usability_summary__lib_uspto50k_excl_v2_freq10_c100.json",
    "reports/bench_multistep__lfreq10_d2b4_n300.json",
    "reports/bench_multistep__lfreq10_d3b4_n300.json",
    "core/query_base.py", "core/smartreact_engine.py", "core/direction.py",
    "sources/herb.py", "sources/chp_priority.py",
    "tools/paper_bench_50k_forward.py", "tools/paper_stats_ci.py",
    "tools/build_chp_markers_2025.py", "tools/curate_chp_markers.py",
    "tools/chp_link_to_db.py", "tools/make_report.py",
    "integration/tcmai_bridge/chemreact.py", "integration/tcmai_bridge/ui.py",
    "reports/paper/论文-v1.0.0-主线与消融统计总表.md",
    "reports/v1.0.0-验收清单（二区投稿就绪）.md",
]

KEYS_101 = [
    "data/formula_source_tier.json", "data/h2_verdicts_all.json", "data/h2_sample.json",
    "data/h2_sample2.json", "data/case_sources.json", "data/gap4_findings.json",
    "data/chp_formulas.json", "data/chp_processed.json", "data/herb_species.json",
    "data/alias_index.json", "data/patch_missing_herbs/patch_tcmdb.sql",
    "data/patch_missing_herbs/missing_herbs.json",
    "sources/formula_source.py", "sources/h2_probe.py",
    "tools/build_formula_source_tier.py", "tools/build_cases_from_db.py",
    "tools/check_herb_naming.py", "tools/run_regression_suite.py",
    "reports/软著/用户手册-v1.0.0-提交版.txt",
    "reports/软著/源程序文档_前30页+后30页.txt",
]


def main() -> int:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    lines, missing, tot = [], [], 0
    keys = KEYS + (KEYS_101 if VERSION != "v1.0.0" else [])
    for rel in keys:
        p = STAGE / rel
        if not p.exists():
            missing.append(rel)
            continue
        h = hashlib.sha256(p.read_bytes()).hexdigest()
        lines.append("%s  %10d  %s" % (h, p.stat().st_size, rel))
        tot += p.stat().st_size
    OUT.write_text("\n".join(lines), encoding="utf-8")
    print("清单 %d 条 · 合计 %.1f MB -> %s" % (len(lines), tot / 1048576, OUT))
    if missing:
        print("缺失（不静默）：")
        for m in missing:
            print("   -", m)
    return 0


if __name__ == "__main__":
    sys.exit(main())
