# -*- coding: utf-8 -*-
r"""发布包：把库/判据表/结果/关键脚本/文档打成一个 zip（含 manifest）。

用法：``python tools\make_release_pack.py [版本号，默认 v1.0.0]``
      v1.0.0 = 冻结版（内容不动）；v1.0.1 = 第七十四~七十五轮增补（出处分档 / 抽检 / 用例 DB 化 / 补库补丁）。
"""
from __future__ import annotations

import sys
import zipfile
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

STAGE = Path(r"D:\ProgramData\DSHNS\chemreact-staging")
REL = STAGE / "reports" / "release"
VERSION = sys.argv[1] if len(sys.argv) > 1 else "v1.0.0"
ZIP = REL / ("chemreact-%s-pack.zip" % VERSION)

# v1.0.1 追加：本轮新增的数据产物、脚本与报告（v1.0.0 冻结物**不动**）
EXTRA_101 = [
    ("data/", ["data/formula_source_tier.json", "data/case_sources.json",
               "data/h2_verdicts_all.json", "data/h2_sample.json",
               "data/h2_sample2.json", "data/gap4_findings.json",
               "data/chp_formulas.json", "data/chp_processed.json",
               "data/herb_species.json", "data/alias_index.json",
               "data/patch_missing_herbs/README.md",
               "data/patch_missing_herbs/missing_herbs.json",
               "data/patch_missing_herbs/patch_tcmdb.sql",
               "data/patch_missing_herbs/rollback_tcmdb.sql"]),
    ("scripts/", ["tools/build_formula_source_tier.py", "tools/build_cases_from_db.py",
                  "tools/h2_verdicts2.py", "tools/h2_merge.py", "tools/h2_report.py",
                  "tools/build_missing_herbs_patch.py", "tools/check_herb_naming.py",
                  "tools/run_regression_suite.py", "tools/make_g2_manual.py"]),
    ("docs/", ["reports/第七十五轮-数据出处隐患.md", "reports/第七十五轮-AI古方抽检.md",
               "reports/第七十五轮-用例DB化-前后.md", "reports/第七十五轮-回归自查.md",
               "reports/第七十五轮-复现演练（B10）.md",
               "reports/第七十五轮-别名缺口与药典剩4味.md",
               "reports/软著/用户手册-v1.0.0-提交版.txt"]),
]

SETS = [
    ("libs/", ["reports/mined_forward_templates_full_lf.jsonl",
               "reports/retro_templates_freq10.jsonl",
               "reports/retro_template_blacklist.json"]),
    ("bench/", ["reports/paper/data/lib_uspto50k_excl_v2.jsonl",
                "reports/paper/data/lib_uspto50k_excl_v2_freq10.jsonl"]),
    ("pharmacopoeia/", ["reports/chp_markers_2025/chp2025_curated.csv",
                        "reports/chp_markers_2025/chp2025_linked.csv",
                        "reports/chp_markers_2025/gold_check.json"]),
    ("results/", ["reports/paper/results/coverage_summary__lib_uspto50k_excl_v2_s10.json",
                  "reports/paper/results/coverage_summary__lib_uspto50k_excl_v2_freq10_s10.json",
                  "reports/paper/results/usability_summary__lib_uspto50k_excl_v2_c100.json",
                  "reports/paper/results/usability_summary__lib_uspto50k_excl_v2_freq10_c100.json",
                  "reports/paper/results/forward_50k.json",
                  "reports/paper/results/forward_50k__full_s10_full50k.json",
                  "reports/paper/results/forward_50k__cap32_20k_full50k.json",
                  "reports/paper/results/forward_50k__lf_cap32_20k_full50k.json",
                  "reports/bench_multistep__lfreq10_d2b4_n300.json",
                  "reports/bench_multistep__lfreq10_d3b4_n300.json"]),
    ("scripts/", ["tools/paper_bench_50k_forward.py", "tools/paper_stats_ci.py",
                  "tools/build_chp_markers_2025.py", "tools/curate_chp_markers.py",
                  "tools/chp_link_to_db.py", "tools/make_report.py",
                  "tools/bench_multistep.py", "tools/build_forward_from_shards_leakfree.py"]),
    ("docs/", ["reports/paper/论文-v1.0.0-主线与消融统计总表.md",
               "reports/paper/复现清单.md", "reports/paper/结果汇总-2026-10-14.md",
               "reports/paper/论文-骨架.md", "reports/paper/草稿-新增章节（EN）.md",
               "reports/v1.0.0-验收清单（二区投稿就绪）.md",
               "reports/第七十轮-交接报告.md"]),
]


def main() -> int:
    REL.mkdir(parents=True, exist_ok=True)
    manifest = REL / "sha256_manifest.txt"
    if VERSION != "v1.0.0":
        manifest = REL / ("sha256_manifest_%s.txt" % VERSION)
    n = 0
    with zipfile.ZipFile(ZIP, "w", zipfile.ZIP_DEFLATED) as z:
        for sub, rels in (SETS + (EXTRA_101 if VERSION != "v1.0.0" else [])):
            for rel in rels:
                p = STAGE / rel
                if not p.exists():
                    print("   [warn] 缺：%s" % rel)
                    continue
                z.write(p, sub + Path(rel).name)
                n += 1
        if manifest.exists():
            z.write(manifest, "docs/sha256_manifest.txt")
            n += 1
    print("打包 %d 个文件 -> %s（%.1f MB）" % (n, ZIP, ZIP.stat().st_size / 1048576))
    return 0


if __name__ == "__main__":
    sys.exit(main())
