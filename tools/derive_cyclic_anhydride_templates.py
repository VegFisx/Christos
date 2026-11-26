# -*- coding: utf-8 -*-
r"""Derive ring-opening O-acylation templates from mapped standard examples.

RDChiral truncates the ring path between the two carbonyls (radius-1
fragments), so its cyclic-anhydride templates either match nothing or produce
ring-split products.  This tool builds the template directly from the mapped
reaction instead:

  reactant: [C:1](=[O:2]) - O:3 - [C:4](=[O:5]) - (ring path back to C:1)
            + [O:6H] - [#6:7]
  product : [C:1](=[O:2])(-[O:6]-[#6:7]) - (same ring path) - [C:4](=[O:5])-[O:3H]

The ring path is taken from the example molecule (shortest path between the
two carbonyl carbons that avoids the bridging oxygen), so each template is
specific to a ring system (succinic / glutaric / phthalic) while staying
generic on the alcohol side.

It only *proposes* templates and validates them on the standard examples and
negatives; it never edits rules/rules.json.
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
for p in (ROOT / "libs", ROOT / "tools", ROOT / "core"):
    sys.path.insert(0, str(p))

from rdkit import Chem, RDLogger
RDLogger.DisableLog("rdApp.*")
from rdkit.Chem import rdChemReactions
from rxnmapper import RXNMapper
import mapped_chem as mc

MAN = ROOT / "data" / "family_standard_examples_20261124.json"
OUT = ROOT / "reports" / "cyclic_anhydride_templates_20261124.json"
FAMILY = "o_acylation"


def key(s):
    m = Chem.MolFromSmiles(s or "")
    if m is None:
        return ""
    return Chem.MolToInchiKey(m)[:14]


def _bfs_excluding(mol, start, goal, blocked):
    """Shortest atom path start->goal that never visits a blocked atom."""
    from collections import deque
    prev = {start: None}
    q = deque([start])
    while q:
        cur = q.popleft()
        if cur == goal:
            out = []
            while cur is not None:
                out.append(cur)
                cur = prev[cur]
            return list(reversed(out))
        for nb in mol.GetAtomWithIdx(cur).GetNeighbors():
            i = nb.GetIdx()
            if i in blocked or i in prev:
                continue
            prev[i] = cur
            q.append(i)
    return None


def atom_query(atom):
    sym = atom.GetSymbol()
    if atom.GetIsAromatic():
        return "[c]" if sym == "C" else "[n]" if sym == "N" else "[#%d]" % atom.GetAtomicNum()
    return "[#%d]" % atom.GetAtomicNum()


def find_center(mol_mapped, broken, formed):
    """Locate (c_attacked, c_other, o_bridge, o_alcohol, c_alcohol) map numbers."""
    pairs = {a.GetProp("molAtomMapNumber"): a.GetIdx()
             for a in mol_mapped.GetAtoms() if a.HasProp("molAtomMapNumber")}
    # bridging O: O with degree 2 bonded to two carbonyl carbons
    o_bridge = None
    carbonyls = []
    for a in mol_mapped.GetAtoms():
        if a.GetSymbol() == "O" and a.GetDegree() == 2 and not a.GetIsAromatic():
            nb = [n for n in a.GetNeighbors() if n.GetSymbol() == "C"]
            if len(nb) == 2 and all(
                    any(b.GetBondTypeAsDouble() == 2.0 for b in n.GetBonds())
                    for n in nb):
                o_bridge = a
                carbonyls = nb
                break
    if o_bridge is None or len(carbonyls) != 2:
        return None
    if not o_bridge.HasProp("molAtomMapNumber"):
        return None
    om = o_bridge.GetProp("molAtomMapNumber")
    broken_set = {(str(a), str(b)) for a, b in broken}
    c_att = None
    for c in carbonyls:
        if not c.HasProp("molAtomMapNumber"):
            continue
        cm = c.GetProp("molAtomMapNumber")
        if (cm, om) in broken_set or (om, cm) in broken_set:
            c_att = cm
    if c_att is None:
        return None
    others = [c.GetProp("molAtomMapNumber") for c in carbonyls
              if c.HasProp("molAtomMapNumber")
              and c.GetProp("molAtomMapNumber") != c_att]
    if not others:
        return None
    c_other = others[0]
    # alcohol O = product O bonded to c_att that is not the carbonyl O / bridge O
    return {"o_bridge": om, "c_att": c_att, "c_other": c_other,
            "idx": {m: i for m, i in pairs.items()}}


def build_template(reactant_smi, product_smi, ex_id, mapper):
    rxn = reactant_smi + ">>" + product_smi
    mapped = mapper.get_attention_guided_atom_maps([rxn])[0].get("mapped_rxn") or ""
    lhs, rhs = mapped.split(">>", 1)
    prod = mc.parse_mapped(rhs)
    left = mc.bonds_over_maps_all([lhs])
    formed, broken = mc.formed_broken(prod, left)
    # anhydride molecule = the reactant fragment carrying the ring
    mol = None
    for frag in lhs.split("."):
        m = Chem.MolFromSmiles(frag)
        if m is not None and m.HasSubstructMatch(
                Chem.MolFromSmarts("[CX3](=[OX1])-[OX2]-[CX3](=[OX1])")):
            mol = m
            break
    if mol is None:
        return None, "no anhydride fragment"
    info = find_center(mol, broken, formed)
    if info is None:
        return None, "no reaction center (bridge/carbonyl not found)"
    idx = info["idx"]
    c_att = idx[info["c_att"]]
    c_other = idx[info["c_other"]]
    o_bridge = idx[info["o_bridge"]]
    # shortest path between the carbonyls that does NOT use the bridging O
    path = _bfs_excluding(mol, c_att, c_other, {o_bridge})
    if path is None:
        return None, "no path between the carbonyls avoiding the bridging O"
    path_idx = [i for i in path if i not in (c_att, c_other)]
    chain = [c_att] + path_idx + [c_other]

    def bond_sym(a, b):
        bt = mol.GetBondBetweenAtoms(a, b).GetBondType()
        return ":" if bt == Chem.BondType.AROMATIC else "-"

    path_atoms = [atom_query(mol.GetAtomWithIdx(i)) for i in path_idx]
    fwd_bonds = [bond_sym(a, b) for a, b in zip(chain, chain[1:])]
    # alcohol: formed bond (c_att, o_alcohol); the O must be an OH in reactants
    o_alc = None
    for a, b in formed:
        if str(a) == info["c_att"] or str(b) == info["c_att"]:
            other = b if str(a) == info["c_att"] else a
            o_alc = str(other)
    if o_alc is None:
        return None, "no formed C-O bond at the attacked carbonyl"
    # which alcohol carbon? find in the reactant fragment with O map o_alc
    c_alc = None
    for frag in lhs.split("."):
        m = Chem.MolFromSmiles(frag)
        if m is None:
            continue
        for a in m.GetAtoms():
            if (a.HasProp("molAtomMapNumber")
                    and a.GetProp("molAtomMapNumber") == o_alc):
                for n in a.GetNeighbors():
                    if n.GetSymbol() == "C":
                        c_alc = n.GetProp("molAtomMapNumber")
        if c_alc:
            break
    if c_alc is None:
        return None, "no alcohol carbon"

    # ---- build full ring-system templates with MolToSmarts ----------------
    # MolToSmarts keeps atom map numbers and emits element-level queries, so
    # the whole anhydride ring system (including fused rings) goes into both
    # sides and nothing is truncated.  Only the alcohol is generalized to
    # [OX2H1]-[#6] (methanol/ethanol/benzyl alcohol/phenol all match).
    fixed = {info["c_att"]: 1, info["o_bridge"]: 3, info["c_other"]: 4}
    for cmap, cmol in ((info["c_att"], c_att), (info["c_other"], c_other)):
        for b in mol.GetAtomWithIdx(cmol).GetBonds():
            nb = b.GetOtherAtom(mol.GetAtomWithIdx(cmol))
            if nb.GetSymbol() == "O" and b.GetBondTypeAsDouble() == 2.0:
                fixed[nb.GetProp("molAtomMapNumber")] = 2 if cmap == info["c_att"] else 5
    new_maps = dict(fixed)
    nxt = 10
    for a in mol.GetAtoms():
        sm = a.GetProp("molAtomMapNumber")
        if sm not in new_maps:
            new_maps[sm] = nxt
            nxt += 1
    new_maps[o_alc] = 8
    new_maps[c_alc] = 9

    react_mol = Chem.RWMol(mol)
    for a in react_mol.GetAtoms():
        a.SetAtomMapNum(new_maps[a.GetProp("molAtomMapNumber")])
    react_mol.UpdatePropertyCache(strict=False)
    react_smarts = Chem.MolToSmarts(react_mol.GetMol())

    keep = set(new_maps)
    prod_mol = Chem.RWMol(prod)
    drop = [a.GetIdx() for a in prod_mol.GetAtoms()
            if not a.HasProp("molAtomMapNumber")
            or a.GetProp("molAtomMapNumber") not in keep]
    for i in sorted(drop, reverse=True):
        prod_mol.RemoveAtom(i)
    for a in prod_mol.GetAtoms():
        a.SetAtomMapNum(new_maps[a.GetProp("molAtomMapNumber")])
    prod_mol.UpdatePropertyCache(strict=False)
    prod_smarts = Chem.MolToSmarts(prod_mol.GetMol())

    smarts = (react_smarts + ".[OX2H1:8]-[#6:9]>>" + prod_smarts)
    try:
        rx = rdChemReactions.ReactionFromSmarts(smarts)
    except Exception as exc:
        return None, "compile fail: %s %s" % (type(exc).__name__, exc)
    skel_mol = Chem.Mol(mol)
    for a in skel_mol.GetAtoms():
        a.SetAtomMapNum(0)
        a.SetChiralTag(Chem.ChiralType.CHI_UNSPECIFIED)
    skel = Chem.MolToSmiles(skel_mol)
    return {"id": ex_id, "smarts": smarts, "ring_path_len": len(path_idx),
            "skeleton": skel}, ""


def run_hit(rx, reactants, target):
    orders = [reactants, list(reversed(reactants))]
    for order in orders:
        ms = [Chem.MolFromSmiles(s) for s in order]
        if any(m is None for m in ms) or len(ms) != rx.GetNumReactantTemplates():
            continue
        try:
            got = rx.RunReactants(tuple(ms))
        except Exception:
            continue
        for ps in got or []:
            for p in ps:
                if p is not None and key(Chem.MolToSmiles(p)) == target:
                    return True
    return False


def main() -> int:
    fam = [x for x in json.loads(MAN.read_text(encoding="utf-8"))["families"]
           if x["name"] == FAMILY][0]
    mapper = RXNMapper()
    by_ring = {}
    for ex in fam["examples"]:
        tpl, err = build_template(".".join(ex["reactants"]), ex["product"],
                                  ex["id"], mapper)
        if tpl is None:
            print("SKIP", ex["id"], err)
            continue
        print("derived", ex["id"], "ring_path", tpl["ring_path_len"])
        print("   ", tpl["smarts"])
        rx = rdChemReactions.ReactionFromSmarts(tpl["smarts"])
        std = []
        for e2 in fam["examples"]:
            if run_hit(rx, e2["reactants"], key(e2["product"])):
                std.append(e2["id"])
        neg = []
        for n in fam.get("negatives") or []:
            if run_hit(rx, n["reactants"], key(n["product"])):
                neg.append(n["id"])
        print("    std", std)
        print("    neg", neg)
        tpl["std_hits"] = std
        tpl["neg_hits"] = neg
        # group by the anhydride skeleton (succinic and phthalic share the
        # same ring-path length but are different ring systems)
        by_ring.setdefault(tpl["skeleton"], []).append(tpl)

    # one template per anhydride skeleton; keep the best (most std hits,
    # then shortest SMARTS)
    report = []
    for skel, items in sorted(by_ring.items()):
        items.sort(key=lambda x: (-len(x["std_hits"]), len(x["smarts"])))
        best = items[0]
        report.append({"skeleton": skel, "ring_path_len": best["ring_path_len"],
                       "smarts": best["smarts"], "source": best["id"],
                       "std_hits": best["std_hits"],
                       "neg_hits": best["neg_hits"]})
    OUT.write_text(json.dumps({"family": FAMILY, "templates": report},
                              ensure_ascii=False, indent=1), encoding="utf-8")
    print("\nwrote", OUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
