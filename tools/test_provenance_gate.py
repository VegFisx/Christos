# -*- coding: utf-8 -*-
"""规则 provenance 闸门的独立验证。

口径：
  · 文件级默认加载（curated_rule_ids=None, allow_unvalidated=False）
    只放 provenance=cited/secondary 的 active 规则；
  · allow_unvalidated=True 才放 unvalidated；
  · 显式 curated_rule_ids 是调用方点名，允许 unvalidated，但必须计数；
  · paozhi_evidence.json 的 18 条必须全部是 cited/secondary。

用法：
    python tools\\test_provenance_gate.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT / "core") not in sys.path:
    sys.path.insert(0, str(ROOT / "core"))

from smartreact_engine import SmartReactEngine  # noqa: E402
import query_base as qb  # noqa: E402

VALIDATED = {"cited", "secondary"}


def load_rules():
    d = json.loads((ROOT / "rules" / "rules.json").read_text(encoding="utf-8"))
    return d.get("rules") if isinstance(d, dict) else d


def load_evidence_ids():
    d = json.loads((ROOT / "rules" / "paozhi_evidence.json").read_text(encoding="utf-8"))
    rs = d.get("rules") if isinstance(d, dict) else d
    return [r["id"] for r in rs if r.get("id")]


def make_engine(**kw):
    base = dict(
        use_curated_templates=True,
        use_extra_templates=False,
        use_mono_templates=False,
        use_base_templates=False,
        gate_conditions=False,
        strict_redox_gate=False,
        rescue=False,
    )
    base.update(kw)
    return SmartReactEngine(**base)


def n_loaded(eng):
    return (len(eng.curated_mono_templates) + len(eng.curated_pair_templates)
            + len(eng.curated_intra_templates))


def main() -> int:
    rules = load_rules()
    active = [r for r in rules
              if str(r.get("status") or "active") == "active"]
    not_paozhi_only = [r for r in active if not r.get("paozhi_only")]
    validated = [r for r in not_paozhi_only
                 if str(r.get("provenance") or "").lower() in VALIDATED]
    unvalidated = [r for r in not_paozhi_only
                   if str(r.get("provenance") or "").lower() not in VALIDATED]
    evidence_ids = load_evidence_ids()
    by_id = {r["id"]: r for r in rules}

    print("rules: total=%d active=%d validated=%d unvalidated=%d evidence=%d"
          % (len(rules), len(active), len(validated), len(unvalidated),
             len(evidence_ids)))

    failures = []

    def check(name, got, want, extra=""):
        ok = got == want
        print("%-4s %-32s got=%s want=%s %s"
              % ("PASS" if ok else "FAIL", name, got, want, extra))
        if not ok:
            failures.append(name)

    # 1. 默认：只放 cited/secondary
    eng = make_engine(allow_unvalidated=False)
    check("default loaded", n_loaded(eng), len(validated))
    check("default skip note", ("跳过 unvalidated %d" % len(unvalidated)) in eng.curated_note,
          True, eng.curated_note)

    # 2. 探索：放全部 active（未标 paozhi_only 的）
    eng2 = make_engine(allow_unvalidated=True)
    check("explore loaded", n_loaded(eng2), len(not_paozhi_only))

    # 3. 显式点名 unvalidated：允许，但计数
    #    不要写死 rule id：规则一旦被证据升级（如 ORD 证据 -> secondary），
    #    写死的 id 就不再是 unvalidated，测试会假失败。
    if not unvalidated:
        raise SystemExit("no active unvalidated rule to test the explicit path")
    probe_id = unvalidated[0]["id"]
    eng3 = make_engine(curated_rule_ids=[probe_id],
                       allow_unvalidated=False)
    check("explicit unvalidated loaded", n_loaded(eng3), 1)
    check("explicit unvalidated note",
          "显式 unvalidated 1" in eng3.curated_note, True, eng3.curated_note)

    # 4. 证据表必须全部是 cited/secondary
    bad_evidence = []
    for rid in evidence_ids:
        r = by_id.get(rid)
        prov = str((r or {}).get("provenance") or "").lower()
        if r is None or prov not in VALIDATED:
            bad_evidence.append((rid, "missing" if r is None else prov))
    check("evidence provenance", bad_evidence, [])

    # 5. 证据表 18 条可全部加载
    eng4 = make_engine(curated_rule_ids=evidence_ids, allow_unvalidated=False)
    check("evidence loaded", n_loaded(eng4), len(evidence_ids))

    # 6. RunSpec -> build_inventory 的开关确实透传（探索比默认多产物）
    def inv_count(allow):
        spec = qb.RunSpec(
            seeds=[("Benzyl alcohol", "OCc1ccccc1", "test")],
            cond_name="煎煮", rounds=1, max_pairs=1, max_products_per_pair=8,
            use_curated_templates=True, use_extra_templates=False,
            use_mono_templates=False, use_base_templates=False,
            allow_unvalidated=allow, rescue=False, stereo_enum_cap=0,
        )
        inv = qb.build_inventory(spec, score=False, use_cache=False)
        return len(inv.paths)

    n_def = inv_count(False)
    n_exp = inv_count(True)
    check("RunSpec default < explore", n_def < n_exp, True,
          "default=%d explore=%d" % (n_def, n_exp))

    print("\nRESULT", "PASS" if not failures else "FAIL",
          "failures=%d" % len(failures))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
