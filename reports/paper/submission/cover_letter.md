# Cover letter (draft)

Dear Editors of PeerJ,

We submit the manuscript "A library-scale audit of template-based retrosynthesis: a few templates dominate false routes and a time-boxed validity criterion is not reproducible" for consideration as a Research Article.

Template-based retrosynthesis is the mainstream engineering path in synthesis planning, and the community has invested heavily in search and ranking. What has not been audited is the template library itself. Our manuscript asks three questions that practitioners cannot currently answer from the literature: whether false routes are spread evenly across a template library or concentrated in a few templates; whether the residue/similarity criterion used to judge route validity is reproducible when its maximum-common-substructure call is time-boxed; and how much recall is lost to candidate truncation rather than to missing templates.

Using a pre-registered, leak-controlled protocol on public data (ORD, USPTO-50k, COCONUT), we report that 54 of 3,025 templates account for 83.8% of wasted cuts, that 68 of 88 MCS invocations (77%) time out in our audit set versus 14.6% in a 50k sample, and that raising the per-pair candidate cap from 8 to 32 lifts single-step recall from 59.40% to 75.80% with zero regressions (McNemar p = 4.1 × 10⁻²⁵). On the full benchmark the leak-free gain is 70.43% to 82.32%. We also show what the field can do about provenance: every template is traced to a reaction identifier, and we demonstrate an ordering basis in which each decision points back to an official pharmacopoeia entry.

The work differs from recent evaluation studies such as Syntheseus (Maziarz et al., 2025) and Models Matter (Torren-Peraire et al., 2024): those audit benchmarks and models, whereas we audit the template library and the truncation behaviour of its search, and we release the audit scripts rather than a new ranker. Negative results are reported as measured, including a controlled-load experiment that failed to exercise the criterion at all.

The manuscript is not under consideration elsewhere, all authors have approved the submission, and we declare no competing interests. Data and code availability are described in the manuscript; no upstream raw data are redistributed.

Yours sincerely,

[Corresponding author name, affiliation, email]
