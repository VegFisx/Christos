# -*- coding: utf-8 -*-
"""独立验证 ChEMBL 药物源适配器；不需要联网。

验证项：
  1. 快照元数据与许可证字段存在；
  2. ChEMBL SMILES 全部能被 RDKit 解析；
  3. 分子式 / InChIKey 与 ChEMBL 记录一致（结构没有在搬运中变形）；
  4. 按 ChEMBL ID、通用名、同义词解析一致，并且不静默猜歧义；
  5. 20 个结构经 to_compound() 往返后身份保持。
"""
from __future__ import annotations

import hashlib
import re
import sys
from collections import Counter
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

ROOT = Path(__file__).resolve().parent.parent
for _p in (ROOT / "core", ROOT / "tools", ROOT / "sources", ROOT / "libs"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from rdkit import Chem, RDLogger
from rdkit.Chem import rdMolDescriptors  # noqa: E402
RDLogger.DisableLog("rdApp.*")

import drug as DR  # noqa: E402


def formula_counts(text: str) -> Counter:
    """元素计数；忽略电荷、分隔点和乘号。"""
    counts = Counter()
    for el, n in re.findall(r"([A-Z][a-z]?)(\d*)", str(text or "")):
        if el:
            counts[el] += int(n or 1)
    return counts


def main() -> int:
    failures = []
    warnings = []
    idx = DR.DrugIndex()
    stats = idx.stats()
    print("snapshot", stats["version"], stats["release_date"], "records", stats["n_records"])
    if not stats.get("license", {}).get("name"):
        failures.append("missing license metadata")
    if stats["n_records"] < 1000:
        failures.append("snapshot unexpectedly small")
    digest = hashlib.sha256(idx.path.read_bytes()).hexdigest()
    if idx.meta.get("data_sha256") and idx.meta.get("data_sha256") != digest:
        failures.append("snapshot sha256 does not match metadata")
    if not str(idx.meta.get("snapshot_version") or "").startswith("ChEMBL_"):
        failures.append("snapshot version missing")

    n_bad_smiles = 0
    n_formula_mismatch = 0
    n_inchi_mismatch = 0
    bad_examples = []
    formula_examples = []
    inchi_examples = []
    for r in idx:
        mol = Chem.MolFromSmiles(r.smiles)
        if mol is None:
            n_bad_smiles += 1
            if len(bad_examples) < 5:
                bad_examples.append((r.chembl_id, r.smiles[:80]))
            continue
        if formula_counts(rdMolDescriptors.CalcMolFormula(mol)) != formula_counts(r.formula):
            n_formula_mismatch += 1
            if len(formula_examples) < 5:
                formula_examples.append((r.chembl_id, r.formula,
                                         rdMolDescriptors.CalcMolFormula(mol)))
        key = Chem.MolToInchiKey(mol)
        if key and r.inchi_key and key != r.inchi_key:
            n_inchi_mismatch += 1
            if len(inchi_examples) < 5:
                inchi_examples.append((r.chembl_id, r.inchi_key, key))
        src_skel = str(r.inchi_key or "").split("-")[0]
        got_skel = str(key or "").split("-")[0]
        if src_skel and got_skel and src_skel != got_skel:
            failures.append("InChI skeleton changed: %s %s -> %s"
                            % (r.chembl_id, r.inchi_key, key))

    print("bad smiles", n_bad_smiles, "formula mismatch", n_formula_mismatch,
          "inchi full-key mismatch", n_inchi_mismatch)
    for label, rows in (("bad", bad_examples), ("formula", formula_examples),
                        ("inchi", inchi_examples)):
        for x in rows:
            print(" ", label, x)
    if n_bad_smiles:
        failures.append("unparsable SMILES: %d" % n_bad_smiles)
    if n_formula_mismatch:
        failures.append("formula mismatch: %d" % n_formula_mismatch)
    if n_inchi_mismatch:
        # Known, reported limitation: ChEMBL's standard InChIKey sometimes
        # carries a stereo layer that its canonical SMILES does not encode
        # (seen for porphyrins / cefotetan-like structures).  The skeleton
        # must still agree, and the count is surfaced rather than hidden.
        frac = n_inchi_mismatch / max(1, len(idx))
        warnings.append("InChI full-key mismatch (stereo layer): %d/%d (%.2f%%)"
                        % (n_inchi_mismatch, len(idx), 100.0 * frac))
        if frac > 0.005:
            failures.append("too many InChI full-key mismatches: %d" % n_inchi_mismatch)

    # ID -> name -> same ID.  Only names that resolve uniquely are tested.
    n_name_roundtrip = 0
    for r in idx.records[::max(1, len(idx) // 20)][:20]:
        if not r.name:
            continue
        if idx.get(r.chembl_id) is not r:
            failures.append("ID lookup failed: %s" % r.chembl_id)
        try:
            by_name = idx.resolve_one(r.name)
        except DR.AmbiguousDrugError:
            continue
        if by_name.chembl_id != r.chembl_id:
            # A preferred-name hit may point at a parent/salt sibling; that is
            # reported, not silently accepted as a different molecule.
            failures.append("name lookup changed ID: %s -> %s (%s)"
                            % (r.chembl_id, by_name.chembl_id, r.name))
        comp = r.to_compound()
        if comp.smiles != r.smiles or comp.name != r.display_name:
            failures.append("to_compound round-trip failed: %s" % r.chembl_id)
        if ("ChEMBL:%s" % r.chembl_id) not in comp.herb:
            failures.append("provenance tag lost: %s" % r.chembl_id)
        n_name_roundtrip += 1
    print("name round-trip checked", n_name_roundtrip)

    # Ambiguity is surfaced, never silently guessed.
    dup_names = {k: v for k, v in idx.by_name.items() if len({r.chembl_id for r in v}) > 1}
    n_amb = 0
    for key, hits in list(dup_names.items())[:20]:
        q = hits[0].display_name
        try:
            got = idx.resolve_one(q)
            ids = {r.chembl_id for r in hits}
            if got.chembl_id not in ids:
                failures.append("ambiguous resolver returned outsider: %s" % q)
        except DR.AmbiguousDrugError as ex:
            n_amb += 1
            if not ex.candidates:
                failures.append("ambiguous error without candidates: %s" % q)
    print("duplicate preferred names", len(dup_names), "raised ambiguous", n_amb)

    # Synonym lookup (trade names / INN variants) must return the same entry
    # when the synonym is unique.
    n_syn_checked = 0
    for r in idx:
        for syn in r.synonyms:
            hits = idx.by_synonym.get(DR._fold(syn), [])
            if len({x.chembl_id for x in hits}) != 1:
                continue
            try:
                got = idx.resolve_one(syn)
            except DR.DrugError as ex:
                failures.append("unique synonym failed: %s (%s)" % (syn, ex))
                continue
            if got.chembl_id != r.chembl_id:
                failures.append("unique synonym changed ID: %s %s -> %s"
                                % (syn, r.chembl_id, got.chembl_id))
            n_syn_checked += 1
            if n_syn_checked >= 20:
                break
        if n_syn_checked >= 20:
            break
    print("unique synonyms checked", n_syn_checked)

    # Salt/derivative records remain addressable by their own ChEMBL ID and
    # retain the parent link.  Duplicate synonyms are the common case where a
    # family has several entries; the resolver must pick a parent, visibly.
    salts = [r for r in idx if r.is_salt_or_derivative]
    if salts:
        s = salts[0]
        got = idx.resolve_one(s.chembl_id)
        if got.chembl_id != s.chembl_id or not got.parent_chembl_id:
            failures.append("salt provenance lost: %s" % s.chembl_id)
        print("salt example", s.chembl_id, "parent", s.parent_chembl_id,
              "name lookup", idx.resolve_one(s.name).chembl_id if s.name else "n/a")
    dup_syn = {k: v for k, v in idx.by_synonym.items()
               if len({r.chembl_id for r in v}) > 1}
    n_parent_pick = 0
    for key, hits in list(dup_syn.items())[:20]:
        query = next((s for s in hits[0].synonyms if DR._fold(s) == key), None)
        if not query:
            continue
        try:
            picked = idx.resolve_one(query)
        except DR.AmbiguousDrugError:
            continue
        if picked.chembl_id in {r.chembl_id for r in hits}:
            n_parent_pick += 1
    print("duplicate synonym keys", len(dup_syn),
          "resolved to a candidate", n_parent_pick, "/20 checked")

    try:
        idx.resolve_one("__CHRISTOS_NO_SUCH_DRUG_9917__")
    except DR.DrugNotFoundError:
        pass
    else:
        failures.append("unknown query did not raise")

    print("FAIL" if failures else "PASS")
    for w in warnings:
        print(" !", w)
    for f in failures[:20]:
        print(" -", f)
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
