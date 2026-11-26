# -*- coding: utf-8 -*-
"""Fetch an offline snapshot of ChEMBL approved small-molecule drugs.

This script is intentionally small and stdlib-only so it can run in the
project's isolated Python.  It does not write to ChEMBL and it does not
invent structures: every SMILES in the snapshot comes from the ChEMBL API.

Example:
    D:\\TCMAI\\venv\\Scripts\\python.exe -I -X utf8 tools\\fetch_chembl_drugs.py

The output is a JSONL file under data/drugs/ plus a metadata JSON sidecar.
The adapter sources/drug.py reads the JSONL in read-only fashion.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DATA_DIR = ROOT / "data" / "drugs"
API_BASE = "https://www.ebi.ac.uk/chembl/api/data"
STATUS_URL = API_BASE + "/status.json"
MOLECULE_URL = API_BASE + "/molecule.json"
LICENSE = {
    "name": "CC BY-SA 3.0 Unported",
    "url": "https://creativecommons.org/licenses/by-sa/3.0/",
    "source": "ChEMBL, European Bioinformatics Institute (EMBL-EBI)",
    "verified_from": "https://www.ebi.ac.uk/chembl/",
    "verified_at": "2026-11-23",
    "attribution": "ChEMBL data are made available under CC BY-SA 3.0; "
                   "attribute ChEMBL/EMBL-EBI and share adaptations alike.",
}
# Only these fields are requested.  The API returns the whole nested
# molecule_structures object (including molfile); it is stripped below.
ONLY_FIELDS = ",".join((
    "molecule_chembl_id", "pref_name", "max_phase", "first_approval",
    "molecule_type", "structure_type", "natural_product", "oral",
    "parenteral", "topical", "black_box_warning", "withdrawn_flag",
    "availability_type", "molecule_hierarchy", "molecule_properties",
    "molecule_structures", "molecule_synonyms",
))


def _log(msg: str) -> None:
    print(msg, flush=True)


def _request_json(url: str, timeout: int = 90, retries: int = 4) -> Dict[str, Any]:
    """GET JSON with bounded retries.  Never silently drops a failed page."""
    last: Optional[BaseException] = None
    for attempt in range(1, retries + 1):
        try:
            req = urllib.request.Request(
                url,
                headers={
                    "User-Agent": "Christos-ChemReact/1.0 (offline ChEMBL snapshot)",
                    "Accept": "application/json",
                },
            )
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                raw = resp.read()
            return json.loads(raw.decode("utf-8"))
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError,
                json.JSONDecodeError) as ex:
            last = ex
            if attempt >= retries:
                break
            wait = min(30, 2 ** attempt)
            _log("  [retry %d/%d] %s: %s (wait %ss)"
                 % (attempt, retries, type(ex).__name__, ex, wait))
            time.sleep(wait)
    raise RuntimeError("ChEMBL request failed: %s: %s" % (type(last).__name__, last))


def _safe_slug(text: str) -> str:
    s = re.sub(r"[^A-Za-z0-9._-]+", "_", str(text or "")).strip("_")
    return s.lower() or "snapshot"


def _num(x: Any) -> Optional[float]:
    try:
        if x is None or x == "":
            return None
        return float(x)
    except (TypeError, ValueError):
        return None


def _int(x: Any) -> Optional[int]:
    v = _num(x)
    return None if v is None else int(v)


def _norm_record(m: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Convert one ChEMBL molecule record to the stable snapshot schema."""
    cid = str(m.get("molecule_chembl_id") or "").strip()
    if not cid:
        return None
    structures = m.get("molecule_structures") or {}
    props = m.get("molecule_properties") or {}
    smiles = str(structures.get("canonical_smiles") or "").strip()
    if not smiles:
        return None
    syn_rows = m.get("molecule_synonyms") or []
    syns: List[str] = []
    seen = set()
    for row in syn_rows:
        if not isinstance(row, dict):
            continue
        s = str(row.get("molecule_synonym") or "").strip()
        if not s:
            continue
        key = s.casefold()
        if key in seen:
            continue
        seen.add(key)
        syns.append(s)
    hierarchy = m.get("molecule_hierarchy") or {}
    return {
        "chembl_id": cid,
        "name": str(m.get("pref_name") or "").strip(),
        "smiles": smiles,
        "inchi": str(structures.get("standard_inchi") or "").strip(),
        "inchi_key": str(structures.get("standard_inchi_key") or "").strip(),
        "formula": str(props.get("full_molformula") or "").strip(),
        "mw": _num(props.get("full_mwt")),
        "heavy_atoms": _int(props.get("heavy_atoms")),
        "max_phase": _num(m.get("max_phase")),
        "first_approval": _int(m.get("first_approval")),
        "molecule_type": str(m.get("molecule_type") or "").strip(),
        "structure_type": str(m.get("structure_type") or "").strip(),
        "parent_chembl_id": str(hierarchy.get("parent_chembl_id") or "").strip(),
        "active_chembl_id": str(hierarchy.get("active_chembl_id") or "").strip(),
        "synonyms": syns,
        "natural_product": bool(m.get("natural_product")),
        "oral": bool(m.get("oral")),
        "parenteral": bool(m.get("parenteral")),
        "topical": bool(m.get("topical")),
        "black_box_warning": bool(m.get("black_box_warning")),
        "withdrawn": bool(m.get("withdrawn_flag")),
        "availability_type": str(m.get("availability_type") or "").strip(),
        "source": "chembl",
    }


def fetch(args: argparse.Namespace) -> int:
    status = _request_json(STATUS_URL, timeout=args.timeout)
    version = str(status.get("chembl_db_version") or "ChEMBL_unknown").strip()
    release_date = str(status.get("chembl_release_date") or "").strip()
    slug = _safe_slug(version)
    data_dir = Path(args.data_dir).resolve() if args.data_dir else DEFAULT_DATA_DIR
    data_dir.mkdir(parents=True, exist_ok=True)
    out = Path(args.out).resolve() if args.out else (data_dir / ("%s_drugs.jsonl" % slug))
    meta_out = (Path(args.meta_out).resolve() if args.meta_out
                else (data_dir / ("%s_meta.json" % slug)))

    records: List[Dict[str, Any]] = []
    seen_ids = set()
    skipped_no_structure = 0
    skipped_not_small = 0
    api_total: Optional[int] = None
    offset = 0
    page = 0
    while True:
        params = {
            "max_phase": str(args.max_phase),
            "limit": str(args.page_size),
            "offset": str(offset),
            "only": ONLY_FIELDS,
        }
        url = MOLECULE_URL + "?" + urllib.parse.urlencode(params)
        page += 1
        payload = _request_json(url, timeout=args.timeout, retries=args.retries)
        molecules = payload.get("molecules") or []
        meta = payload.get("page_meta") or {}
        if api_total is None:
            api_total = _int(meta.get("total_count"))
        for m in molecules:
            if not isinstance(m, dict):
                continue
            mtype = str(m.get("molecule_type") or "").strip().lower()
            structs = m.get("molecule_structures") or {}
            if not str(structs.get("canonical_smiles") or "").strip():
                skipped_no_structure += 1
                continue
            if args.molecule_type and mtype != args.molecule_type.strip().lower():
                skipped_not_small += 1
                continue
            rec = _norm_record(m)
            if rec is None:
                skipped_no_structure += 1
                continue
            if rec["chembl_id"] in seen_ids:
                continue
            seen_ids.add(rec["chembl_id"])
            records.append(rec)
        _log("  page %d: API %d/%s  kept %d"
             % (page, offset + len(molecules), api_total, len(records)))
        nxt = meta.get("next")
        if not nxt or not molecules:
            break
        if args.max_records and len(records) >= args.max_records:
            records = records[:args.max_records]
            break
        offset += len(molecules)
        if args.sleep:
            time.sleep(args.sleep)

    # Stable order: ChEMBL ID numeric where possible, then lexical.
    def _key(r: Dict[str, Any]) -> Tuple[int, str]:
        digits = re.sub(r"\D", "", r.get("chembl_id") or "")
        return (int(digits) if digits else 10 ** 12, r.get("chembl_id") or "")

    records.sort(key=_key)
    tmp = out.with_suffix(out.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n")
    os.replace(str(tmp), str(out))

    digest = hashlib.sha256(out.read_bytes()).hexdigest()
    meta = {
        "snapshot_version": version,
        "release_date": release_date,
        "downloaded_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "api_base": API_BASE,
        "query": {"max_phase": args.max_phase,
                  "molecule_type": args.molecule_type or "(all)"},
        "api_total": api_total,
        "n_records": len(records),
        "n_skipped_no_structure": skipped_no_structure,
        "n_skipped_not_small_molecule": skipped_not_small,
        "data_file": out.name,
        "data_sha256": digest,
        "fields": [
            "chembl_id", "name", "smiles", "inchi", "inchi_key", "formula",
            "mw", "heavy_atoms", "max_phase", "first_approval",
            "molecule_type", "structure_type", "parent_chembl_id",
            "active_chembl_id", "synonyms", "natural_product", "oral",
            "parenteral", "topical", "black_box_warning", "withdrawn",
            "availability_type", "source",
        ],
        "license": LICENSE,
        "note": ("Snapshot for local reaction enumeration. No structures were "
                 "hand-written. max_phase=4 represents approved drugs in ChEMBL; "
                 "phase is not a guarantee of current marketing status."),
    }
    meta_out.write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n",
                        encoding="utf-8")
    _log("")
    _log("ChEMBL snapshot: %s (%s)" % (version, release_date))
    _log("  records: %d  api_total: %s" % (len(records), api_total))
    _log("  skipped: no_structure=%d not_small_molecule=%d"
         % (skipped_no_structure, skipped_not_small))
    _log("  data: %s" % out)
    _log("  meta: %s" % meta_out)
    _log("  sha256: %s" % digest)
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="Fetch ChEMBL approved-drug snapshot")
    ap.add_argument("--max-phase", type=float, default=4.0, dest="max_phase",
                    help="ChEMBL max_phase filter (default 4.0 = approved)")
    ap.add_argument("--molecule-type", default="Small molecule",
                    dest="molecule_type",
                    help="molecule_type filter; empty string keeps all types")
    ap.add_argument("--page-size", type=int, default=1000, dest="page_size")
    ap.add_argument("--max-records", type=int, default=0, dest="max_records",
                    help="stop after N kept records (0 = all)")
    ap.add_argument("--data-dir", default=None, dest="data_dir")
    ap.add_argument("--out", default=None)
    ap.add_argument("--meta-out", default=None, dest="meta_out")
    ap.add_argument("--timeout", type=int, default=90)
    ap.add_argument("--retries", type=int, default=4)
    ap.add_argument("--sleep", type=float, default=0.25,
                    help="seconds between API pages")
    args = ap.parse_args()
    if args.page_size <= 0 or args.page_size > 1000:
        ap.error("--page-size must be 1..1000")
    return fetch(args)


if __name__ == "__main__":
    raise SystemExit(main())
