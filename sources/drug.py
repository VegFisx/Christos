# -*- coding: utf-8 -*-
"""Read-only ChEMBL drug source for Christos/ChemReact.

Drugs are treated as another *input source*, not as a new rule set.  The
adapter preserves the ChEMBL ID, preferred name, synonyms, approval phase and
snapshot version so every downstream product can be traced back to a source
structure.  It never writes to ChEMBL and never invents a SMILES.

Snapshot layout (created by tools/fetch_chembl_drugs.py):
    data/drugs/chembl_37_drugs.jsonl
    data/drugs/chembl_37_meta.json

Override with CHEMREACT_DRUG_DB=/path/to/*_drugs.jsonl.
"""
from __future__ import annotations

import json
import os
import re
import sys
import unicodedata
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, Sequence, Tuple

_HERE = Path(__file__).resolve().parent
_STAGE = _HERE.parent
for _p in (_STAGE / "core",):
    if _p.is_dir() and str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from engine import Compound  # noqa: E402

DATA_DIR = _STAGE / "data" / "drugs"
ENV_SNAPSHOT = "CHEMCREACT_DRUG_DB"
LAST_RESOLVE: Dict[str, Any] = {}


class DrugError(Exception):
    """Base class for drug-source errors."""


class DrugNotFoundError(DrugError):
    def __init__(self, query: str, suggestions: Optional[Sequence["DrugRecord"]] = None):
        self.query = query
        self.suggestions = list(suggestions or [])
        msg = "未找到药物 %r" % query
        if self.suggestions:
            msg += "；候选：" + "; ".join(
                "%s (%s)" % (r.name or "?", r.chembl_id) for r in self.suggestions[:8])
        super().__init__(msg)


class AmbiguousDrugError(DrugError):
    def __init__(self, query: str, candidates: Sequence["DrugRecord"]):
        self.query = query
        self.candidates = list(candidates)
        msg = "药物名 %r 对应 %d 个 ChEMBL 条目，请改用 ChEMBL ID" % (
            query, len(self.candidates))
        super().__init__(msg)


def _fold(text: str) -> str:
    """Name key: NFKC, casefold, keep only letters/digits."""
    s = unicodedata.normalize("NFKC", str(text or "")).casefold()
    return re.sub(r"[^0-9a-z\u0080-\uffff]+", "", s)


def _as_bool(v: Any) -> bool:
    return bool(v)


def _as_float(v: Any) -> Optional[float]:
    try:
        if v is None or v == "":
            return None
        return float(v)
    except (TypeError, ValueError):
        return None


def _as_int(v: Any) -> Optional[int]:
    n = _as_float(v)
    return None if n is None else int(n)


@dataclass(frozen=True)
class DrugRecord:
    chembl_id: str
    name: str
    smiles: str
    inchi: str = ""
    inchi_key: str = ""
    formula: str = ""
    mw: Optional[float] = None
    heavy_atoms: Optional[int] = None
    max_phase: Optional[float] = None
    first_approval: Optional[int] = None
    molecule_type: str = ""
    structure_type: str = ""
    parent_chembl_id: str = ""
    active_chembl_id: str = ""
    synonyms: Tuple[str, ...] = ()
    natural_product: bool = False
    oral: bool = False
    parenteral: bool = False
    topical: bool = False
    black_box_warning: bool = False
    withdrawn: bool = False
    availability_type: str = ""
    source: str = "chembl"

    @property
    def display_name(self) -> str:
        return self.name or self.chembl_id

    @property
    def is_salt_or_derivative(self) -> bool:
        return bool(self.parent_chembl_id and self.parent_chembl_id != self.chembl_id)

    @property
    def is_approved(self) -> bool:
        return self.max_phase is not None and self.max_phase >= 4.0

    def provenance(self) -> Dict[str, Any]:
        return {
            "chembl_id": self.chembl_id,
            "name": self.name,
            "source": self.source,
            "max_phase": self.max_phase,
            "first_approval": self.first_approval,
            "parent_chembl_id": self.parent_chembl_id,
            "active_chembl_id": self.active_chembl_id,
            "formula": self.formula,
            "inchi_key": self.inchi_key,
            "withdrawn": self.withdrawn,
            "is_salt_or_derivative": self.is_salt_or_derivative,
        }

    def to_compound(self) -> Compound:
        """Return an engine Compound tagged with its ChEMBL provenance."""
        return Compound(
            smiles=self.smiles,
            name=self.display_name,
            herb="药物:ChEMBL:%s" % self.chembl_id,
            source="user",
        )

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["synonyms"] = list(self.synonyms)
        return d


def _candidate_key(rec: DrugRecord) -> Tuple[int, int, int, str]:
    """Prefer free parent, approved, non-withdrawn, then stable ID."""
    return (
        0 if not rec.is_salt_or_derivative else 1,
        0 if not rec.withdrawn else 1,
        0 if rec.is_approved else 1,
        rec.chembl_id,
    )


def _pick_one(query: str, hits: Sequence[DrugRecord]) -> DrugRecord:
    uniq = {r.chembl_id: r for r in hits}
    vals = list(uniq.values())
    if len(vals) == 1:
        return vals[0]
    vals.sort(key=_candidate_key)
    best_key = _candidate_key(vals[0])
    tied = [r for r in vals if _candidate_key(r) == best_key]
    if len(tied) == 1:
        return tied[0]
    raise AmbiguousDrugError(query, vals)


def _snapshot_meta(path: Path) -> Dict[str, Any]:
    cands = [
        path.with_name(path.name.replace("_drugs.jsonl", "_meta.json")),
        path.with_name(path.stem + ".meta.json"),
        path.with_suffix(path.suffix + ".meta.json"),
    ]
    for p in cands:
        if p.exists():
            try:
                return json.loads(p.read_text(encoding="utf-8"))
            except Exception:
                return {}
    return {}


def _default_snapshot() -> Path:
    env = str(os.environ.get(ENV_SNAPSHOT) or "").strip()
    if env:
        p = Path(env)
        if not p.exists():
            raise DrugError("环境变量 %s 指向的文件不存在：%s" % (ENV_SNAPSHOT, p))
        return p
    if not DATA_DIR.is_dir():
        raise DrugError("未找到 ChEMBL 快照目录：%s" % DATA_DIR)
    paths = sorted(DATA_DIR.glob("*_drugs.jsonl"))
    if not paths:
        raise DrugError(
            "未找到 ChEMBL 快照。先运行：\n"
            "  D:\\TCMAI\\venv\\Scripts\\python.exe -I -X utf8 "
            "tools\\fetch_chembl_drugs.py")
    # Prefer the highest numeric ChEMBL release, not merely the newest mtime.
    def key(p: Path):
        m = re.search(r"chembl_(\d+)", p.name, re.I)
        return (int(m.group(1)) if m else -1, p.name)
    return max(paths, key=key)


class DrugIndex:
    """In-memory index over an offline ChEMBL JSONL snapshot."""

    def __init__(self, snapshot: Optional[os.PathLike | str] = None):
        self.path = Path(snapshot).resolve() if snapshot else _default_snapshot().resolve()
        if not self.path.exists():
            raise DrugError("ChEMBL 快照不存在：%s" % self.path)
        self.meta = _snapshot_meta(self.path)
        self.records: List[DrugRecord] = []
        self.n_duplicate_ids = 0
        seen = set()
        with open(self.path, "r", encoding="utf-8") as f:
            for lineno, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue
                try:
                    raw = json.loads(line)
                except json.JSONDecodeError as ex:
                    raise DrugError("快照第 %d 行不是合法 JSON：%s" % (lineno, ex))
                if not isinstance(raw, dict) or raw.get("_meta"):
                    continue
                cid = str(raw.get("chembl_id") or "").strip()
                smiles = str(raw.get("smiles") or "").strip()
                if not cid or not smiles:
                    continue
                if cid in seen:
                    self.n_duplicate_ids += 1
                    continue
                seen.add(cid)
                syns = raw.get("synonyms") or []
                if not isinstance(syns, list):
                    syns = []
                self.records.append(DrugRecord(
                    chembl_id=cid,
                    name=str(raw.get("name") or "").strip(),
                    smiles=smiles,
                    inchi=str(raw.get("inchi") or "").strip(),
                    inchi_key=str(raw.get("inchi_key") or "").strip(),
                    formula=str(raw.get("formula") or "").strip(),
                    mw=_as_float(raw.get("mw")),
                    heavy_atoms=_as_int(raw.get("heavy_atoms")),
                    max_phase=_as_float(raw.get("max_phase")),
                    first_approval=_as_int(raw.get("first_approval")),
                    molecule_type=str(raw.get("molecule_type") or "").strip(),
                    structure_type=str(raw.get("structure_type") or "").strip(),
                    parent_chembl_id=str(raw.get("parent_chembl_id") or "").strip(),
                    active_chembl_id=str(raw.get("active_chembl_id") or "").strip(),
                    synonyms=tuple(str(x).strip() for x in syns if str(x).strip()),
                    natural_product=_as_bool(raw.get("natural_product")),
                    oral=_as_bool(raw.get("oral")),
                    parenteral=_as_bool(raw.get("parenteral")),
                    topical=_as_bool(raw.get("topical")),
                    black_box_warning=_as_bool(raw.get("black_box_warning")),
                    withdrawn=_as_bool(raw.get("withdrawn")),
                    availability_type=str(raw.get("availability_type") or "").strip(),
                    source=str(raw.get("source") or "chembl").strip() or "chembl",
                ))
        if not self.records:
            raise DrugError("ChEMBL 快照为空：%s" % self.path)
        self.by_id: Dict[str, DrugRecord] = {r.chembl_id: r for r in self.records}
        self.by_name: Dict[str, List[DrugRecord]] = {}
        self.by_synonym: Dict[str, List[DrugRecord]] = {}
        for r in self.records:
            if r.name:
                self.by_name.setdefault(_fold(r.name), []).append(r)
            for s in r.synonyms:
                self.by_synonym.setdefault(_fold(s), []).append(r)

    @property
    def version(self) -> str:
        return str(self.meta.get("snapshot_version") or self.path.stem)

    @property
    def release_date(self) -> str:
        return str(self.meta.get("release_date") or "")

    def __len__(self) -> int:
        return len(self.records)

    def __iter__(self) -> Iterator[DrugRecord]:
        return iter(self.records)

    def get(self, chembl_id: str) -> Optional[DrugRecord]:
        return self.by_id.get(str(chembl_id or "").strip().upper())

    def suggest(self, query: str, limit: int = 10) -> List[DrugRecord]:
        q = _fold(query)
        if not q:
            return []
        out: List[DrugRecord] = []
        seen = set()
        for r in self.records:
            hay = _fold(r.name) + "|" + "|".join(_fold(s) for s in r.synonyms)
            if q in hay:
                if r.chembl_id not in seen:
                    seen.add(r.chembl_id)
                    out.append(r)
            if len(out) >= limit:
                break
        return out

    def search(self, query: str = "", limit: int = 20) -> List[DrugRecord]:
        q = str(query or "").strip()
        if not q:
            return self.records[:max(0, limit)]
        return self.suggest(q, limit=limit)

    def resolve_one(self, query: str) -> DrugRecord:
        """Resolve exactly; raise on no match or ambiguity instead of guessing."""
        q = str(query or "").strip()
        if not q:
            raise DrugNotFoundError(q)
        # 1) ChEMBL ID, tolerant of case / separators.
        cid = re.sub(r"[^A-Za-z0-9]", "", q).upper()
        if re.fullmatch(r"CHEMBL\d+", cid):
            hit = self.get(cid)
            if hit is not None:
                out = hit
                LAST_RESOLVE.clear()
                LAST_RESOLVE.update({"query": q, "matched": out.chembl_id,
                                     "how": "ChEMBL ID", "n_candidates": 1})
                return out
            raise DrugNotFoundError(q, self.suggest(q))
        # 2) Approved/preferred name, then synonyms.  A name hit beats a
        # synonym hit; ambiguity is surfaced with IDs rather than resolved.
        key = _fold(q)
        for table, how in ((self.by_name, "preferred name"),
                           (self.by_synonym, "synonym")):
            hits = table.get(key) or []
            if not hits:
                continue
            n_candidates = len({r.chembl_id for r in hits})
            out = _pick_one(q, hits)
            LAST_RESOLVE.clear()
            LAST_RESOLVE.update({"query": q, "matched": out.chembl_id, "how": how,
                                 "n_candidates": n_candidates})
            return out
        raise DrugNotFoundError(q, self.suggest(q))

    def stats(self) -> Dict[str, Any]:
        n = len(self.records)
        n_salt = sum(1 for r in self.records if r.is_salt_or_derivative)
        n_no_formula = sum(1 for r in self.records if not r.formula)
        n_no_key = sum(1 for r in self.records if not r.inchi_key)
        n_withdrawn = sum(1 for r in self.records if r.withdrawn)
        n_np = sum(1 for r in self.records if r.natural_product)
        return {
            "snapshot": self.path.name,
            "version": self.version,
            "release_date": self.release_date,
            "n_records": n,
            "n_salt_or_derivative": n_salt,
            "n_withdrawn": n_withdrawn,
            "n_natural_product": n_np,
            "n_missing_formula": n_no_formula,
            "n_missing_inchi_key": n_no_key,
            "n_duplicate_ids": self.n_duplicate_ids,
            "license": self.meta.get("license") or {},
        }

    def format_record(self, r: DrugRecord) -> str:
        flags = []
        if r.withdrawn:
            flags.append("withdrawn")
        if r.is_salt_or_derivative:
            flags.append("salt/derivative of %s" % r.parent_chembl_id)
        extra = ("; " + ", ".join(flags)) if flags else ""
        return "%s  %s  max_phase=%s%s" % (
            r.chembl_id, r.display_name, r.max_phase if r.max_phase is not None else "?",
            extra)


def load_index(snapshot: Optional[os.PathLike | str] = None) -> DrugIndex:
    return DrugIndex(snapshot)


def _main(argv: Optional[Sequence[str]] = None) -> int:
    import argparse
    ap = argparse.ArgumentParser(description="ChEMBL drug source (read-only)")
    ap.add_argument("--snapshot", default=None)
    ap.add_argument("--stats", action="store_true")
    ap.add_argument("--search", default=None)
    ap.add_argument("--resolve", default=None)
    ap.add_argument("--list", type=int, default=0)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    try:
        idx = DrugIndex(args.snapshot)
    except DrugError as ex:
        print("ERROR:", ex)
        return 2
    if args.stats:
        print(json.dumps(idx.stats(), ensure_ascii=False, indent=2))
        return 0
    if args.resolve:
        try:
            r = idx.resolve_one(args.resolve)
        except DrugError as ex:
            print("ERROR:", ex)
            if isinstance(ex, AmbiguousDrugError):
                for c in ex.candidates[:20]:
                    print("  ", idx.format_record(c))
            elif isinstance(ex, DrugNotFoundError):
                for c in ex.suggestions[:10]:
                    print("  ", idx.format_record(c))
            return 1
        print(json.dumps(r.to_dict(), ensure_ascii=False, indent=2)
              if args.json else idx.format_record(r))
        return 0
    rows = idx.search(args.search or "", limit=(args.list or 20))
    for r in rows:
        print(idx.format_record(r))
    if not rows:
        print("(no matches)")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
