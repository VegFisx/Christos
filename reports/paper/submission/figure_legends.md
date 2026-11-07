# Figure legends (PeerJ submission)

Upload each file in `figures/` separately; PNG is 300 dpi, PDF is vector. Legends go in the manuscript or the submission system as indicated.

**Figure 1.** Concentration of invalid disconnections in the 56-target audit set. Templates are ranked by the number of wasted cut attempts; the curve gives the cumulative share of wasted cuts. Fifty-four of 3,025 templates (red marker) account for 83.8% of all wasted attempts.

**Figure 2.** Chemically usable cuts before and after blacklisting, on the 56-target audit set and on the USPTO-50k sample (2,930 targets). Values above the bars are percentages.

**Figure 3.** Reactant-set match rate on USPTO-50k (50,016 targets, 3,065 leak-free templates). `any` is the existence of a correct disconnection; top-k is the best rank of the correct disconnection under frequency-then-lexicographic ordering.

**Figure 4.** Composition of single-step cut verdicts (usable / R1 residue / R2 enlargement / R3 inert / R4 absurd) in the 56-target audit set and in the USPTO-50k sample.

**Figure 5.** Share of maximum-common-substructure (MCS) calls that time out under the 2 s box. Annotations give the second run of the same 56-target audit (66/87) and the historical replication difference between two independent audits (3 of 414 cuts).

**Figure 6.** Forward single-step recall by reaction class in the baseline configuration. The dashed line marks the overall recall of 55.43%; because the protocol supplies reactants only (no reagents or catalysts), C–C coupling classes are structurally disadvantaged.

**Figure 7.** (A) Truncation saturation: single-step any-hit on a 500-reaction ablation as the per-pair candidate cap increases from 8 to 32 to 64, for a sweet-spot pool (3k/1.5k) and a full pool (20k/6k). (B) End-to-end multi-step success at depth ≤ 2 and ≤ 3 (beam = 4, n = 300, leak-free library) with Wilson 95% confidence intervals; the cross marks the n = 100 pilot.
