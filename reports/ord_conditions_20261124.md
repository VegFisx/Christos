# ORD conditions for product-match records

- rules: 41
- scanned records: 120000
- rules with water in a matching record: **40**
- water AND temp <= 100 C: **33**
- at least 3 such records: 24
- at least 10 such records: 11
- water-only solvent AND temp <= 100 C: **23**
- water-only AND <= 100 C AND no metal catalyst: **23**

| rule | matches | <=100C no metal | water-only | water-only&<=100C | water-only&<=100C&no metal | water | water&<=100C |
|---|---:|---:|---:|---:|---:|---:|---:|
| `hydrolysis_amide_001` | 3362 | 428 | 98 | 24 | 24 | 236 | 68 |
| `amidation_intermolecular_001` | 6006 | 648 | 46 | 16 | 16 | 591 | 120 |
| `coupling_suzuki_biaryl_001` | 920 | 200 | 46 | 19 | 15 | 227 | 105 |
| `hydrolysis_lactam_001` | 2750 | 320 | 59 | 13 | 13 | 152 | 42 |
| `esterification_intermolecular_001` | 998 | 182 | 43 | 13 | 13 | 66 | 19 |
| `aminolysis_ester_001` | 1249 | 236 | 45 | 10 | 10 | 120 | 40 |
| `reduction_ketone_001` | 955 | 199 | 30 | 7 | 7 | 76 | 14 |
| `oxidation_sulfide_001` | 336 | 78 | 20 | 6 | 6 | 61 | 11 |
| `hydrolysis_acetal_001` | 213 | 40 | 21 | 6 | 6 | 36 | 8 |
| `oxidation_hydroxyl_001` | 346 | 68 | 9 | 3 | 3 | 41 | 14 |
| `reduction_aldehyde_001` | 313 | 61 | 10 | 3 | 3 | 24 | 6 |
| `esterification_transesterification_001` | 321 | 43 | 14 | 3 | 3 | 28 | 4 |
| `coupling_sonogashira_aryl_alkyne_001` | 287 | 85 | 3 | 2 | 2 | 10 | 8 |
| `reduction_alkene_001` | 747 | 49 | 19 | 2 | 2 | 35 | 7 |
| `condensation_schiff_base_001` | 142 | 13 | 6 | 2 | 2 | 8 | 3 |
| `demethylation_aromatic_001` | 686 | 140 | 35 | 2 | 2 | 49 | 3 |
| `oxidation_sulfoxide_to_sulfone_001` | 26 | 7 | 3 | 2 | 2 | 6 | 3 |
| `oxidation_aldehyde_001` | 126 | 29 | 6 | 1 | 1 | 56 | 19 |
| `condensation_aldol_001` | 75 | 31 | 1 | 1 | 1 | 17 | 9 |
| `elimination_amide_to_nitrile_001` | 122 | 25 | 6 | 1 | 1 | 12 | 3 |
| `hydroxylation_aromatic_001` | 35 | 6 | 4 | 1 | 1 | 12 | 3 |
| `acylation_alcohol_anhydride_001` | 145 | 24 | 6 | 1 | 1 | 11 | 2 |
| `substitution_alcohol_thionyl_family_001` | 307 | 52 | 3 | 1 | 1 | 6 | 2 |
| `oxidation_primary_alcohol_001` | 524 | 105 | 5 | 0 | 0 | 38 | 16 |
| `coupling_n_alkylation_benzyl_001` | 63 | 7 | 7 | 0 | 0 | 12 | 5 |
| `hydration_alkene_001` | 70 | 15 | 1 | 0 | 0 | 19 | 4 |
| `coupling_n_arylation_amine_001` | 149 | 19 | 0 | 0 | 0 | 5 | 2 |
| `acylation_alcohol_cyclic_succinic_001` | 18 | 4 | 0 | 0 | 0 | 2 | 1 |
| `decarboxylation_aromatic_001` | 58 | 3 | 5 | 0 | 0 | 8 | 1 |
| `elimination_deamination_001` | 13 | 3 | 0 | 0 | 0 | 2 | 1 |
| `oxidation_amine_001` | 13 | 3 | 0 | 0 | 0 | 2 | 1 |
| `oxidation_dehydrogenation_enone_001` | 41 | 8 | 3 | 0 | 0 | 4 | 1 |
| `oxidation_epoxide_001` | 103 | 22 | 3 | 0 | 0 | 10 | 1 |
| `addition_michael_amine_001` | 76 | 15 | 6 | 0 | 0 | 6 | 0 |
| `addition_michael_thiol_001` | 28 | 2 | 0 | 0 | 0 | 2 | 0 |
| `cyclization_macro_lactam_001` | 14 | 0 | 0 | 0 | 0 | 0 | 0 |
| `decarboxylation_beta_keto_001` | 13 | 0 | 1 | 0 | 0 | 1 | 0 |
| `decarboxylation_malonic_001` | 13 | 0 | 1 | 0 | 0 | 1 | 0 |
| `hydrolysis_imine_001` | 21 | 4 | 1 | 0 | 0 | 4 | 0 |
| `isomerization_double_bond_001` | 22 | 2 | 5 | 0 | 0 | 6 | 0 |
| `rearrangement_retro_aldol_001` | 15 | 0 | 1 | 0 | 0 | 1 | 0 |
