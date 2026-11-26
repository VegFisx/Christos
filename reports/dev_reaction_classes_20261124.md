# Dev miss reaction classes (2026-11-24)

Source: `dev_general_organic_20261124.json`, full_lf baseline (195/300).
Misses: **105**; RXNMapper mapped **105/105**; no silent failures.
Method: RXNMapper + `mapped_chem.formed_broken`; classify by element pairs of
formed/broken bonds. This is a **dev-only** analysis; blind1 was not used.

## Bond-change classes

| class | n |
|---|---:|
| C–N formed | 34 |
| C–C formed | 29 |
| C–O formed | 14 |
| C–Cl formed | 9 |
| C–Br formed | 4 |
| C–O cleaved + C–O formed | 3 |
| C–C + C–O formed | 3 |
| C–S formed | 3 |
| C–I formed | 1 |
| N–N formed | 1 |
| C–C cleaved + C–C/C–O formed | 1 |
| O–Si formed | 1 |
| C–C cleaved + C–C formed | 1 |
| N–S formed | 1 |

## What the classes mean

- **C–N (34)** is the largest. The examples are mostly amide/sulfonamide/urea
  coupling on substrates that already carry protecting groups or other
  functional groups. The four new rules (Boc/Cbz deprotection, sulfonylation,
  isocyanate-urea) cover only a small subset; they do not explain the 34.
- **C–C (29)** is the next largest: aryl–aryl/alkyl–aryl coupling and
  cyclization, not a single named reaction.
- **C–O (14)**: O-alkylation/esterification/ether formation.
- **C–Cl (9)** and **C–Br (4)**: chlorination/bromination, often with
  SOCl2 or similar; not a target for the current rule set.
- The remaining classes are single digits.

## Consequence

The next rule batch should target **generic C–N coupling on protected
substrates** and **C–C coupling**, not more deprotection rules. Each added rule
must still start from an independent standard example and pass standard,
held-out, negative and balance checks. `blind1` stays sealed; any new rule is
evaluated on a fresh blind set, not this dev set.

Machine-readable details: `reports/dev_reaction_classes_20261124.json`.
