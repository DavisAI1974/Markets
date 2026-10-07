# Step 3 module and interface review — 2026-10-07

SOURCE-BUILT / RUNTIME-UNVERIFIED. Reviewed the current source from `439cb0b`, preserving concurrent work.
Applied using-agent-skills, context-engineering, API and Interface Design, performance-optimization, and the AWS
`aws-compute` skill with `references/systems-manager.md` (documentation retrieval only). The current handoff and
Greg's source-only hold override generic skill instructions to execute tests, profile, or inspect AWS.

## Current interface map

Paths below are under `deploy/aws/box/` unless stated otherwise. Source locations describe this review's working tree.

| Module / boundary | Actual contract and consumer | Limit that remains |
|---|---|---|
| `frankie_box_experiment_data.py:124` `plan`, `:165` `export` | Catalog dispositions and selected completed native evidence become owner-local hard links with byte/hash pins in `MANIFEST.json`. Private reasoning and graded answers have distinct exclusions. | Export selection is not calculation consumption. Old/unselected producer outputs are not activated. |
| `frankie_box_experiment_search.py:245` `columns`, `:457` `build_series` | Every scalar/list-position leaf; exact Python integers, separate mixed-type channels, collision refusal. Six returned objects: axis, series, cells, sources, notes, gates. F_LAST frame order remains the axis. | Positional leaves are not persistent order trajectories. `build_series` docstring still lists only five outputs; callers correctly unpack six. |
| `frankie_box_experiment_journal.py:36` `_frame_index`, `:72` `read_columns` | Complete normal INPUT/APPLIED envelopes join exact ROOT membership, preserving ordered within-group slots; original unplaced ordinals remain explicit. | Failed/unpaired/unclosed/unmatched envelopes do not become invented earlier market states. |
| `frankie_box_experiment_native.py:26` `selected_files`, `:91` `read_columns` | Completed pinned member/lifecycle ledgers join INPUT cursor, instrument and receive identity; all nested leaves and ordered emissions reach the existing axis. | Native producer activation remains opt-in; FINALIZE evidence is completed knowledge, not an earlier live feature. Full registry/consumer closure is unproven. |
| `frankie_box_experiment_search.py:332` `root_row_columns` | Structure V1 and price V2 use explicit membership/provenance. Price slots retain originating INPUT and emitting close. Legacy timestamp aliases remain separately named. | V1 trade origins/opening-state origins are not guessed. Aliases are duplicate representations, not independent observations. |
| `frankie_box_experiment_dipole.py:24` `read_columns` | Snapshot/export/source-prefix verification; exact APPLIED cursors; every original row slot, entity closing row, current component, raw values under PRESENT masks and retained DState leaves. | Existing target/mask semantics stay intact. This does not establish all native learner supervision or identity-linked trajectories. |
| `frankie_box_experiment_surface.py:70` `external_fields`; search `:843` | All external table columns per explicit native entity, native publication stamps, existing aliases retained. Market quantities become series; lawful IDs/calendar categories condition observations. | Identity/stamp columns are listed, and as-of aliases explicitly account for overwritten/unplaced original rows. |
| `frankie_box_experiment_search.py:133` `non_market_reason` | Role exclusions occur after identity/clock/mask use. Dates/IDs remain grouping context; actual prices, spreads, flow, FIFO age and geometry remain quantities. | These disposition rules do not prove full producer or semantic coverage. |
| `frankie_box_experiment_transforms.py:27–153`; search `:1048`, `:1263` | Five unchanged causal transforms, all selected x/y transform combinations on distinct series; exact pair/cell/day counts through the existing FFT statistic/chance check. | Pairwise nonlinear transforms do not implement multivariable symbolic fitting. |
| `frankie_box_scientific_teacher.py:625` `row_scope_reasons`, `:675` `test` | Scoped historical/Frankie/Jev/search claims consume hash-bound saved counts; unapplied conditions, mismatched lag/transform/cell and non-market roles are `counts_only`. | A counts-only receipt is not a tested condition or completed historical rework. |
| `frankie_box_experiment.py:1695` `Run.search`; `frankie_box_frankie_queue.py:943` `_finish_day` | Owner-local data/search/review path; owning day runs the teacher step before export/search, including non-classroom days. Search workers derive from held lane CPUs minus coordinator. | Runtime/old receipt behavior remains unverified; no E2E follows from the source trace. |
| Search `:1006–1045`, `:1263–1483` | Cooperative stop drains submitted operations; prepared arrays and completed work bind to source/helper/code identities; retained cursors and output hashes guard resume/publication. | Abrupt unsupported interruption is retained/refused, not claimed recovered. |
| `odcore/symbolic.py:69` `discover`; `scripts/od_pysr_discover.py:61,67` | Existing PySR equation discovery with original operators, fitting objective and per-run output is preserved. | Not called by the experiment search/teacher path. Its fixed operator-column contract requires a lawful feature/target mapping; no substitute mathematics or activation was added. |

## Narrow changes made

1. **Transform receipt accuracy:** search manifest `transforms.pairs` now uses exactly the same selected-y predicate
   (`ty in steps`) and x→y orientation as `_cell_job.partners`. Previously a subset request advertised all five
   registry transforms despite calculating only that subset. Full default roster, pair counts and math are unchanged.
2. **Exact alignment reuse:** the `build_series.asof` closure at `:545` retains the source-ordinal vector already
   needed for selection accounting, then gathers every numeric leaf from it after its unchanged per-field leakage
   gate. This removes repeated identical sort/search work across leaves. The same `asof_source_rows` function still
   owns valid clocks, stable ties and selection; `-1` still produces `None`, values keep object dtype, and no field or
   original source row is dropped. The vector is local to one source/clocks call, not a cross-source/day cache.
3. Updated the stale opening price description to the existing V2 exact-price contract.
4. **Boundary refusals:** `search:1331` now requires a nonnegative integer lag radius, and `:1344` requires unique
   transform names before staging state is created. Negative lag radii previously produced an empty best-lag range;
   duplicate transform names previously submitted duplicate jobs with colliding retained output paths. Neither request
   is silently repaired. Worker allocation remains the existing owner-lane contract; no standalone cap was invented.

The source hash in the existing continuation identity changes with these edits, so an older prepared continuation
cannot silently reuse a different reader implementation. No retained artifact was rewritten.

## Concrete open defects and smallest next changes

- **Conditional lag changes its unit:** search `:1283` selects `v[idx]` for both x and y before `couple` at `:1309`.
  Lag one therefore means the next selected cell occurrence, not the next original F_LAST group. Cell membership
  is attached to the arriving step at `:1420`. This is the previously documented axis defect, not a newly settled
  mathematical choice. Smallest next interface work: preserve the original axis and pass an explicit predictor
  condition mask into counts/null handling; settle the precise null/condition contract before changing the statistic.
- **Confirmation discards frozen lag scope:** search `:1359–1361` retains only transforms, series and cell in its
  survivor key; `couple:979` again maximizes over all candidate lags. Retaining pair identity is not retesting the
  frozen lag. Smallest next work: bind lag and scope in survivor/candidate interfaces and consume the bound lag with
  its existing scientific semantics. Do not apply the preserved draft or invent a replacement chance statistic.
- **Uncalled conditions and targets:** `surface.state_masks:95` and `journal_axis:10` have no active search call.
  Numeric conditions, native-event lag units, new fill/exhaustion target definitions and full symbolic routing remain
  open. Existing fill-count and Dipole series do not establish those missing target definitions. Reuse the present
  helpers and symbolic engine only after their causal feature/target/condition contracts are settled.

## AWS options and performance disposition

Only public AWS documentation and skill text were retrieved; no instances, metrics, volumes, commands or account
configuration were inspected. Exactly three existing held 16-CPU lanes, each 15 workers plus coordinator, remain.

| Evaluated option | Decision for this step |
|---|---|
| Tune work on the existing EC2 lane before changing infrastructure | Applied the local exact-alignment reuse above. AWS's [EC2 CPU tuning guide](https://aws.amazon.com/blogs/compute/tuning-guide-for-amd-amazon-ec2-instances/) recommends examining workload tuning before resizing/scaling. No claim is made about the held instances' processor family or measured bottleneck. |
| More process concurrency / larger or extra EC2 instance | Not applied. `_run_pending` already bounds in-flight jobs, and `Run.search` supplies 15 workers on the held 16-CPU lane. Extra workers/lane capacity would violate the current allocation and lack performance evidence. |
| AWS Batch / managed parallel fleets | Not applied. [AWS Batch workflow guidance](https://aws.amazon.com/blogs/compute/building-high-throughput-genomic-batch-workflows-on-aws-batch-layer-part-3-of-4/) describes managed provisioning from queued CPU needs; adopting it would introduce an unrequested service/resource lifecycle instead of reusing the owning lane. |
| EBS throughput / IOPS tuning | Deferred. [AWS EBS quota guidance](https://repost.aws/knowledge-center/ec2-instance-ebs-quotas) explains that instance and volume ceilings both constrain performance and distinguishes large sequential throughput from small-file IOPS. Actual storage limits and bottlenecks are unknown under the account-inspection hold; no volume mutation or price assumption was made. |
| Systems Manager | Keep the existing control route. The retrieved `aws-compute/references/systems-manager.md` describes managed execution and command-output auditing; it is not a scientific processing accelerator. No SSM command or new service was introduced. |

The speedup is an inference from removed repeated work, **not measured performance**. Per source with C numeric
leaves, ordinary source-to-axis sort/search previously ran once for accounting and again per leaf; it now runs once.
Every field's leakage checks and every output gather still run. The temporary ordinal vector uses int64 storage and
is released with the source closure call. No tests, benchmarks, synthetic execution, project imports, model/data calls,
installations, AWS account reads/actions, dispatch, compute, commit or push occurred in this slice.

Verification: source/diff inspection, `ast.parse` without project imports, and `git diff --check` only. Step 3 stays open;
the one real E2E remains separately held, as does thirty-day execution.
