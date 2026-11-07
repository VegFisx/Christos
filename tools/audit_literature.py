#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""一条命令跑完文献可信度三步核对（元数据 → 引句 → 汇总）。

链条：
    1. DOI 是否注册、标题/期刊/年份与 Crossref 是否一致   （tools/verify_citations.py）
    2. 引句是否出现在正文或摘要里                         （tools/verify_quotes.py）
    3. 合并成一份 summary，给出通过/警告/失败计数与退出码

本脚本**只读**：不写回任何证据文件（写回要用 tools/apply_citation_check.py）。

退出码：
    0 = 全部通过（可能有"摘要级"或"付费刊"警告）
    1 = 有 DOI 未注册，或引句在可读文本里找不到
    2 = 脚本自身失败（网络全断等）

用法：
    python tools/audit_literature.py [-o reports/literature_audit.json] [--quick]
"""
import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

ROOT = Path(__file__).resolve().parents[1]
PY = sys.executable


def run(script, extra=()):
    """跑一个子脚本，返回 (exit_code, tail_output)。"""
    cmd = [PY, "-I", str(ROOT / "tools" / script)] + list(extra)
    r = subprocess.run(cmd, cwd=str(ROOT), capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    tail = "\n".join((r.stdout or "").strip().splitlines()[-6:])
    if r.returncode != 0:
        tail += "\n[stderr] " + "\n".join((r.stderr or "").strip().splitlines()[-6:])
    return r.returncode, tail


def load(rel):
    p = ROOT / rel
    if not p.exists():
        return None
    return json.loads(p.read_text(encoding="utf-8"))


EVIDENCE_FILES = [
    "rules/paozhi_evidence.json",
    "rules/literature_evidence.json",
    "conditions/kinetics_measurements.json",
    "conditions/template_verification_20261106.json",
    "reports/paper/paozhi_sources_20261031.json",
]


def acknowledged_dois():
    """证据文件里已明确标了 doi_valid: false 的 DOI —— 属已知问题，不算新故障。"""
    out = set()
    for rel in EVIDENCE_FILES:
        p = ROOT / rel
        if not p.exists():
            continue
        txt = p.read_text(encoding="utf-8")

        def _walk(obj):
            if isinstance(obj, dict):
                if obj.get("doi_valid") is False and isinstance(obj.get("doi"), str):
                    out.add(obj["doi"].strip().lower())
                for v in obj.values():
                    _walk(v)
            elif isinstance(obj, list):
                for v in obj:
                    _walk(v)

        try:
            _walk(json.loads(txt))
        except Exception:
            pass
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("-o", "--out", default="reports/literature_audit.json")
    ap.add_argument("--quick", action="store_true", help="跳过引句核对（只查元数据）")
    args = ap.parse_args()

    t0 = time.time()
    print("=" * 78)
    print("第 1 步：DOI 元数据核对（Crossref / EuropePMC / OpenAlex / doi.org）")
    print("=" * 78)
    rc1, tail1 = run("verify_citations.py", ["-o", "reports/citation_check.json"])
    print(tail1)
    cit = load("reports/citation_check.json")

    quotes = None
    rc2 = 0
    tail2 = "(skipped)"
    if not args.quick:
        print("\n" + "=" * 78)
        print("第 2 步：引句回原文核对（EuropePMC 全文 → 摘要）")
        print("=" * 78)
        rc2, tail2 = run("verify_quotes.py", ["-o", "reports/quote_check.json"])
        print(tail2)
        quotes = load("reports/quote_check.json")

    c_cit = (cit or {}).get("counts", {})
    c_q = (quotes or {}).get("counts", {})

    bad_doi = c_cit.get("doi_not_registered", 0) + c_cit.get("not_found", 0)
    # 已知问题（证据文件里已标 doi_valid: false）不算新故障
    ack = acknowledged_dois()
    new_bad_doi = 0
    bad_list = []
    for r in (cit or {}).get("rows", []):
        if r.get("status") in ("not_found", "doi_not_registered"):
            d = r["doi"].lower()
            if d in ack:
                continue
            new_bad_doi += 1
            bad_list.append(r["doi"])
    bad_quote = c_q.get("absent", 0)
    warn_quote = c_q.get("abstract_absent", 0) + c_q.get("no_full_text", 0)
    warn_meta = (c_cit.get("metadata_mismatch", 0)
                 + c_cit.get("not_in_crossref_resolvable", 0))

    print("\n" + "=" * 78)
    print("汇总")
    print("=" * 78)
    print("DOI 记录：%s" % json.dumps(c_cit, ensure_ascii=False))
    if quotes:
        print("引句判定：%s" % json.dumps(c_q, ensure_ascii=False))
    print("")
    print("  DOI 未注册/查不到（含已知 %d 条已标 doi_valid:false）: %d" % (len(ack), bad_doi))
    print("  其中**新出现**的（需要处理）: %d %s" % (new_bad_doi, bad_list[:5]))
    print("  致命（引句在可读文本里找不到）: %d" % bad_quote)
    print("  警告（元数据不一致 / 中文库 DOI）: %d" % warn_meta)
    print("  警告（只核到摘要 / 拿不到文本）: %d" % warn_quote)
    print("  耗时 %.1f s" % (time.time() - t0))

    code = 0
    if rc1 != 0 or rc2 != 0:
        code = 2
    elif new_bad_doi or bad_quote:
        code = 1

    out = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "steps": {
            "citations": {"script": "tools/verify_citations.py", "exit": rc1,
                          "counts": c_cit, "tail": tail1},
            "quotes": {"script": "tools/verify_quotes.py", "exit": rc2,
                       "counts": c_q, "tail": tail2},
        },
        "fatal": {"doi_total": bad_doi, "doi_new": new_bad_doi,
                  "doi_new_list": bad_list, "quote_absent": bad_quote},
        "acknowledged_dois": sorted(ack),
        "warnings": {"metadata_mismatch": warn_meta, "quote_abstract_or_missing": warn_quote},
        "exit_code": code,
        "note": ("只读汇总；写回证据文件请用 tools/apply_citation_check.py。"
                 "abstract_* 表示全文付费、但摘要里命中；no_full_text 表示全文与摘要都没拿到。"
                 "退出码 1 只代表**新出现**的 DOI 未注册或引句找不到；已标 doi_valid:false 的不算。"),
    }
    p = ROOT / args.out
    p.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print("\n退出码 %d，写出 %s" % (code, p))
    return code


if __name__ == "__main__":
    sys.exit(main())
