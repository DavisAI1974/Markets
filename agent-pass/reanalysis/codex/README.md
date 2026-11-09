# Codex independent report

The report and supporting artifacts are saved separately from Ccode's work. There is no reconciliation, joint synthesis or automatic cross-report comparison. Both use the same frozen evidence and both analyze behavior→price and price→subsequent market behavior.

Read [REPORT.md](REPORT.md), then [PAPER_STRATEGIES.md](PAPER_STRATEGIES.md), [PAPER_READINESS.md](PAPER_READINESS.md) and [OPEN_QUESTIONS.md](OPEN_QUESTIONS.md). [RECEIPT.json](RECEIPT.json) pins the shared brief, evidence, code, report and data revisions.

## Evidence ledgers
All data files are in the [immutable analysis publication](https://github.com/DavisAI1974/markets-data/tree/8c761b486d4a9910d77eedad83ae23078c971bee/tasks/family-research-20261022/codex-independent-analysis/run-42599646462-1). CSV fields referring to REPORT.md sections resolve to [this Markets report](https://github.com/DavisAI1974/Markets/blob/864a9fa1b98c3e8ee446a3bb30068ea4fbbe5a5f/agent-pass/reanalysis/codex/REPORT.md).

| Deliverable | Contents |
| --- | --- |
| [CLAIMS.csv](https://github.com/DavisAI1974/markets-data/blob/8c761b486d4a9910d77eedad83ae23078c971bee/tasks/family-research-20261022/codex-independent-analysis/run-42599646462-1/CLAIMS.csv) | 30 interpreted claim groups, evidence, contrary cases, availability and limits |
| [RELATIONSHIP_ROWS.csv.gz](https://github.com/DavisAI1974/markets-data/blob/8c761b486d4a9910d77eedad83ae23078c971bee/tasks/family-research-20261022/codex-independent-analysis/run-42599646462-1/RELATIONSHIP_ROWS.csv.gz) | 209,020 original saved comparison/summary rows from 191 tables; no weak/adverse-row filter |
| [PRICE_RESPONSE_RELATIONSHIPS.csv](https://github.com/DavisAI1974/markets-data/blob/8c761b486d4a9910d77eedad83ae23078c971bee/tasks/family-research-20261022/codex-independent-analysis/run-42599646462-1/PRICE_RESPONSE_RELATIONSHIPS.csv) | All 170 prior-displacement/quote-change comparisons from the cross-day coupling table |
| [CASES.csv](https://github.com/DavisAI1974/markets-data/blob/8c761b486d4a9910d77eedad83ae23078c971bee/tasks/family-research-20261022/codex-independent-analysis/run-42599646462-1/CASES.csv) | 22 supplied illustrative cases across all four dates, original clocks, IDs and source rows |
| [COVERAGE.csv](https://github.com/DavisAI1974/markets-data/blob/8c761b486d4a9910d77eedad83ae23078c971bee/tasks/family-research-20261022/codex-independent-analysis/run-42599646462-1/COVERAGE.csv) | Every one of 1,296 distinct input contents; companion field shards preserve 223,428 flattened field paths |
| [SOURCE_ALIASES.csv](https://github.com/DavisAI1974/markets-data/blob/8c761b486d4a9910d77eedad83ae23078c971bee/tasks/family-research-20261022/codex-independent-analysis/run-42599646462-1/SOURCE_ALIASES.csv) | 163 duplicate source coordinates retained as aliases |
| [CONFLICTS.csv](https://github.com/DavisAI1974/markets-data/blob/8c761b486d4a9910d77eedad83ae23078c971bee/tasks/family-research-20261022/codex-independent-analysis/run-42599646462-1/CONFLICTS.csv) | Exact conflicting statements/records, valid contrary cases and definition differences |
| [DIPOLE_LAYER_MAP.csv](https://github.com/DavisAI1974/markets-data/blob/8c761b486d4a9910d77eedad83ae23078c971bee/tasks/family-research-20261022/codex-independent-analysis/run-42599646462-1/DIPOLE_LAYER_MAP.csv) | All 99 canonical names plus 9 source-defined analytical aspects, clearly distinguished |
| [SUPPORTING_PACKET_COVERAGE.csv](https://github.com/DavisAI1974/markets-data/blob/8c761b486d4a9910d77eedad83ae23078c971bee/tasks/family-research-20261022/codex-independent-analysis/run-42599646462-1/SUPPORTING_PACKET_COVERAGE.csv) | 65 lifecycle/external/context files and their field ledger |
| [BULK_CLOCK_ANNOTATION_REFERENCE.json](https://github.com/DavisAI1974/markets-data/blob/8c761b486d4a9910d77eedad83ae23078c971bee/tasks/family-research-20261022/codex-independent-analysis/run-42599646462-1/BULK_CLOCK_ANNOTATION_REFERENCE.json) | Original 553-source clock catalogs and summary, separate from market-event counts |
| [UNAVAILABLE_REFERENCES.json](https://github.com/DavisAI1974/markets-data/blob/8c761b486d4a9910d77eedad83ae23078c971bee/tasks/family-research-20261022/codex-independent-analysis/run-42599646462-1/UNAVAILABLE_REFERENCES.json) | Three historical archive references retained explicitly |
| [SUMMARY.json](https://github.com/DavisAI1974/markets-data/blob/8c761b486d4a9910d77eedad83ae23078c971bee/tasks/family-research-20261022/codex-independent-analysis/run-42599646462-1/SUMMARY.json) / [VERIFICATION.json](https://github.com/DavisAI1974/markets-data/blob/8c761b486d4a9910d77eedad83ae23078c971bee/tasks/family-research-20261022/codex-independent-analysis/run-42599646462-1/VERIFICATION.json) / [MANIFEST.json](https://github.com/DavisAI1974/markets-data/blob/8c761b486d4a9910d77eedad83ae23078c971bee/tasks/family-research-20261022/codex-independent-analysis/run-42599646462-1/MANIFEST.json) | Counts, assertions and measured output hashes |

The [source review publication](https://github.com/DavisAI1974/markets-data/tree/e2731854a42bcce04a8cf89e249603dc18d3b0f7/tasks/family-research-20261022/codex-independent-review/run-42594360842-1) contains complete structural inventory, whole-file field statistics and schema examples. Examples are the first three and final records; every applicable row contributes to structural statistics. This is source accounting, not a claim of visual or causal understanding.

## Coverage limits
The final field ledger gives class-level interpretation for 180,022 flattened paths and marks 43,406 pending detailed semantics/units. Paths include nested dictionary keys, per-second keys and metadata; these are not 223,428 distinct predictors. This report does not claim every field is fully understood. Unknown fields remain retained and must be resolved from their producer before supporting a decision claim.

All 1,296 active input byte counts/hashes passed; 65 manifested supporting files were also read. Images retain source links but not every render was visually inspected. Raw DBN bytes were verified and completed reconstruction receipts reused without rerunning producers. Three historical archive directory references remain unavailable as files. No new normalized paths, producer suite, paper order or live-money action was created.

## Verification and correction precedence
- [Source review run 42594360842](https://github.com/DavisAI1974/markets-data/actions/runs/42594360842): success.
- [Final ledger run 42599646462](https://github.com/DavisAI1974/markets-data/actions/runs/42599646462): success; source/field conservation, 99-layer count, exact integer case clocks and corrected directional counts checked.
- The earlier run 42598562586 is superseded by the final ledger publication: the final version carries the actual three unavailable reference records instead of only their count, reads the correct shard catalogs, and improves source-specific field interpretation. Original market observations were unchanged.
- The authoritative signed-pair correction is [DIRECTIONAL_PROSE_CORRECTION.json](https://github.com/DavisAI1974/markets-data/blob/8c761b486d4a9910d77eedad83ae23078c971bee/tasks/family-research-20261022/codex-independent-analysis/run-42599646462-1/DIRECTIONAL_PROSE_CORRECTION.json): five signed pairs exceed the saved line on three dates, one on two, four on one, none on all four.
- The corrected shared Tier 1 nanosecond annotations remain authoritative through the unchanged frozen evidence packet.

Paper configurations are explicit experimental specifications with unverified NG routing, fees and fill behavior. They are observation-only and not deployed. See the readiness list; written rules are not measured profitable strategies.
