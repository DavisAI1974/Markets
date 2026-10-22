# Family research continuation, 2026-10-22

Continues the complete handoff at `9064cdf69bc6fa23fd37380b68dbe1538cd26025`.
V3 remains frozen. The full coverage gate remains **NOT_PASSED**. No v4 matrix
or full-coverage model result is claimed. The complete certified rerun remains owed.

## Latest user steering: one pass, start Julia promptly

### Superseding execution change: 63 workers on the same AWS instance

The user requested parallel processes and immediate redeployment. The initial
two-process executor is superseded by `parallel-63/` within the candidate output
directory. The matrix build finished and its 26/26 preparation checks passed;
initial fits began at 16:17:41 UTC. All computations use the AWS machine's RAM.

The parallel executor has 63 compute slots: four prepared-fold jobs plus up to
59 fit jobs during preparation, and 63 fit slots after preparation. Julia, BLAS,
OpenMP and MKL are restricted to one CPU thread per worker. A single read-only
34,601,642,880-byte matrix is memory-mapped, with prepared folds also shared;
workers do not each deserialize a private copy of the complete matrix.

The one runtime deployment pass (`a2909877-6781-4c31-b324-7c4f2a8215dd`) observed
63 Julia workers, 95.7% machine CPU utilization, 13 completed isolated fit jobs,
zero job errors, and 79,353,332 KiB available RAM. Disk-cache admission is bounded
and completed dense fold caches can be reproduced from the frozen inputs; model
states, raw data, provenance, failed records and metadata are retained.

Eight committed serial neural results are kept and skipped in the new queue.
Uncommitted core states/logs are preserved in `parallel-63/serial-prefix` and are
not promoted to completed results. Targets, family splits, embargo, seeds,
hyperparameters and epoch counts are unchanged. Thread-count changes can affect
floating-point last bits; no bit-identical fit claim is made. The full semantic
coverage gate remains NOT_PASSED, so this remains a candidate benchmark.

Use `parallel-redeploy.log`, `parallel-63/parallel_plan.json` and isolated
`parallel-63/jobs/*/job_receipt.json` for current execution status. The initial
`run_suite.sh` launcher and two fit processes were stopped after their outputs
were preserved. No instance lifecycle action, monitor, agent, chat or live order
was created.

The user requested one verification pass and Julia running within ten minutes.
At 16:04:54 UTC on October 22, the expanded candidate suite was launched, about
six minutes after that instruction. Julia build PID `15138`; launcher PID
`15137`; launch SSM `9b544398-ee63-4ac4-8186-85b17bebb6f6`.

Persistent candidate input/output directories:
`joint-inputs-v4-candidate-20261022` and
`joint-models-v4-candidate-20261022`. This explicitly labelled candidate benchmark
does **not** certify the full 99-plane semantic gate. The manifest retains that
gate as NOT_PASSED, with unresolved units/knowledge mappings visible. V3 stays
frozen. Do not silently relabel this as a fully covered V4 result.

The suite builds the expanded matrix, performs the single existing rules check,
then starts the original core and neural model suites. Targets, chronological
folds, family separation, purge/600-second embargo, training-only preprocessing,
fixed seeds and neural epochs stay as declared. No prior fitted states are copied.
Core includes constant/ridge/EvoTrees shallow/deep/MAE/quantiles/group/history
refits and PCA/k-means; neural includes neural tree, residual MLP and TabM.
Build/start is not model completion. Inspect actual output receipts for results.

## Additional completed components

- Normalized all 7,679,916 provenance records from 19 sources, across 38,677
  dimensional scopes. All 270 canonical field roles have explicit dispositions.
  The original raw/catalog files are unchanged. The new Oct17 version is included.
- Preserved coincident curve messages: 343,700 additional same-stamp source
  occurrences are retained. Content hashes and coarse observation IDs are not
  substituted for event counts.
- Resolved 5,275,928 observation states using exact availability before primary
  precedence. Retained 45,220 unranked numeric conflict cells and 389,931 primary
  unavailable cells; no alternate fill of a primary null/deletion/missing marker.
- Consumed every resolved observation into scoped historical timelines: 20,380,668
  numeric emissions, 6,349,614 categorical emissions, 187,766 timeline rows and
  1,652,923 registered feature/clock roles. This does not create extra aligned
  market days. Units and final semantic coverage remain incomplete.
- Full ROOT extraction: 6,265 contexts; 2,786,032 level aliases, 6,993,462
  identity-linked FIFO order observations, zero future order-update clocks.
  Ordered snapshots do not establish unobserved continuous survival or true birth.
- Stricter native/second feature-identity checks found zero collisions across
  66,911 identities, comparing 29,497,352 numeric and 858,166 categorical cells
  exactly with the already saved extraction. The old payload was not rewritten.
- Episode audit: 1,726 opening/complete records correspond to 863 candidates,
  862 complete paths and one withheld NO_PREDECESSOR path; 54,042 stages.
  Actual full-row emissions and cursor caps are retained, including censoring.
- Every stage-book assignment matches the canonical caller hypothesis. Every
  assigned book arrived later than its stage bin. Strictly past books differ at
  45,879 stages, with midpoint differences at 8,925 stages and different coupling
  on 671 paths. Both views are saved; midpoint coupling is not executable return.
- Explicit source-rule phase reconstruction keeps event phase separate from
  stage octave, session phase and orientation: 1,319 BIRTH, 51,861 PERSISTENCE,
  862 REVERSAL stages. These are labelled reconstructions with actual row
  availability, not directly stored stage fields or backdated input signals.
- Exact bid/ask exports cover all 10,486 model contexts and 749 families.
  12,530 full-depth conservation and 12,530 touch-price checks passed. All 6,265
  selected unique snapshots were two-sided. Consecutive-window data is separate.
- 59 local Python tests passed before the candidate build was launched. No new
  rounds of broad verification are being added after the user's one-pass request.

Semantic review notes and explicitly unresolved mappings are saved in
`knowledge-semantic-review-working-notes.md`. All 72 canonical source files are
recovered; a complete file-level semantic-review count is not yet established.

## New durable archives

Bucket `bento-568968024170-us-east-2-an`, region `us-east-2`, common key prefix
`frankie/family-prebirth/20261022/`:

| Archive | Bytes | SHA256 |
| --- | ---: | --- |
| `full-context-continuation-v1-eb2b860d.tar.gz` | 181035517 | `eb2b860d452d1a462ef609e44a8c6aad4b89d71f28d9de049b15b3b6c585e4e1` |
| `external-history-v4-normalized-v1-2e6808cf.tar.gz` | 3788033203 | `2e6808cf2e1ca07e89ae3260d237d81327418dd28a1710c81ba7f0b733b656b0` |
| `dipole-book-clock-audit-v1-b3be15d9.tar.gz` | 3898548 | `b3be15d9d60f9e2d9a6465ef68c3ad731d871324474e1d0b5e5fad8c315ce471` |
| `asof-quotes-phases-v1-258d1951.tar.gz` | 1833955983 | `258d1951e16029d3b42222da7e6145ae3e6f807f24f654b3c24f7b925cea696b` |

The first three archives have HTTP-200 uploads, local downloads and all 35 member
hashes verified in one transport pass. The as-of/quotes/phases archive has an
HTTP-200 upload; its receipt is saved separately. It has not been downloaded locally.
Large archives remain outside Git; compact receipts, registries, code and
scientific comparisons are saved in the repository.

## Original external classroom: completed reproduction

- Reconstructed the exact original 48 series and 211,055 known values from the
  saved primary database, with all 771,787 second-set rows and the original
  receive-time cutoff `1697662799696377528`.
- Checked all 2,040 original external relationships. Endpoint counts match the
  original report: 663 opposite, 632 same, 745 unresolved. Pearson availability
  matches: 1,333 reported, 16 insufficient, 691 zero variance. Julia's Pearson
  reduction is not asserted bit-identical to original OpenBLAS-32 arithmetic.
- All **441/441** filed claims reproduce their endpoint relations and all five
  step counts exactly. External values remain Float64, native classroom values
  Float32; raw native Float64 is a separately named sensitivity.
- Saved 10,419 summary rows, 88,071 exact alignment segments, all state-pair
  counts and the original scoped rows. Quarter, precision and adjacency
  sensitivities cover the 441 filed pairs; original checks cover all 2,040.
- Retained 1,128 overlapping open flags: endpoint/path 441, chronological
  reversal 226, missing-group bridge sensitivity 353, raw precision 46,
  individual versus matched endpoint support 62. These counts overlap and
  must not be added to other registries as independent discoveries.
- Python tests: 28 passed. New exact-nanosecond Julia alignment tests: 5/5.
  SSM component execution `7b930f30-12e3-4082-95cd-f89e8e178186`; contradiction
  review `1eac3771-15a7-4936-bd03-2c8aefadce9b`.

Reproduced hypotheses remain open scientific questions. Adjacent group
ordinals do not prove reset-free continuity. No prospective, causal or
tradable effect has been established. Full history alignment and semantic
knowledge/source coverage are separate unfinished requirements.

## Durable component save

Persistent AWS directory:
`/opt/frankie-box/work/family-research-20261022/external-classroom-audit-v1`.

Archive key (bucket `bento-568968024170-us-east-2-an`, region `us-east-2`):
`frankie/family-prebirth/20261022/external-classroom-audit-v1-99fb865d.tar.gz`.
11,654,997 bytes; SHA256
`99fb865d41874f949c90090872fc6e5d1b27e219310777416c36d813b6ce8579`.
Uploaded with HTTP 200; downloaded and all 18 manifest member hashes verified
locally. Complete reconstructed rows stay in the archive/persistent input file.
Code, checks, flags, segments and receipts are saved beside this status file.

## Additional recoverable history located and saved

The handoff identified a newer prior-day `20231017` object. Recovered exactly
that named object with an If-Match ETag guard; no recovery-directory scan.
38,223,416 bytes, ETag `3e4b06be7d420227f6c4eb597167f0d1`, SHA256
`8c9bf49fda3adf984c191ed06c13ee7c04117777a9535b485c9cbe15400e2c71`.
Saved under persistent `full-context-audit/historical-source-additions/`.
This additional version is normalized and included in the scoped historical
timeline described above. The previous history catalog remains unchanged.
Original publication stamps, explicit reader placements, dimensional scopes and
unresolved source variants remain available; no favorable revision is selected
to fill a current primary missing value.
