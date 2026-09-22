# The Sunday-slice sites and the schedule shapes, mapped 2026-09-22 (a read-only sweep by an Explore agent; advisory input to modules 2-4)

Produced in chat 9 at Greg's "Build everything and just leave the things we need from ingest blank". Every line names a
file:line where the first run's Sunday-slice identity (57,027 records, 19 steps, one UTC date, "full Sunday source") is a
literal or a gate, and what it guards; then the data shapes of the schedule, the binding, the seeds, the host runner's
flow and the re-pin workflow. Verify each line against the code before changing it; the capability map's list stands.
(Non-ASCII characters of the agent's text were replaced; 1 distinct ones: 0x2208)

# Sunday-identity -> trading-day: site map + data shapes (read-only, branch `claude/cycle-0-monday-rerun-hk2q2z`)

Repo root `/home/user/Markets`; package root `/home/user/Markets/research/kalshi/frankie_boss` (abbrev. `FB/` below = that dir). No edits made.

---

## A. THE SITE MAP - one line per site

Format: `file:line - exact expression - what it guards`

### A1. The `57027` record count (the "one measurement")

1. `FB/selected_source_scope.py:17` - `size_bytes=973355, mbo_records=57027)])` - **the declared source identity itself**. This literal is inside `source_manifest()`, whose body is hashed by `manifest_hash(body)`; `source_scope()` (l.23-25) refuses anything that is not byte-identical: `if (manifest != source_manifest() or expected_manifest_hash != manifest['manifest_hash']): raise ValueError('source differs from the independently pinned single-source scope')`. Changing 57027 here changes `scope.genesis_hash()` and therefore invalidates every downstream hash (`scope_hash 7460b519...`). Root of the whole chain.
2. `FB/selected_source_scope.py:15` - `member_key='glbx-mdp3-20211003.mbo.dbn.zst'` - same manifest: **one member, one UTC partition, pinned filename + sha256 `4380bd9b...`**. The Monday partition cannot be added without a new module (see `block_source_scope.py`, A6).
3. `FB/operations/run_actual_sunday.py:351-353` - `if (receipt['record_count']!=57027 or completion['record_count']!=57027 or outer['source_records']!=57027 or outer['steps']!=19 or outer['source_completion']!=completion): raise ValueError('full Sunday source and nineteen-step schedule required')` - **the host's source() refusal**; gates ingestion receipt + completion.json + schedule receipt at once. Four gates in one expression (three counts + one step count).
4. `FB/operations/run_actual_sunday.py:452` - `receipt['source_records_expected']!=57027` (inside the `prefix()` conjunction l.446-453, `raise ValueError('actual prefix snapshot differs from full source and authored cutoff')`) - **per-cycle prefix snapshot refusal**: each prefix receipt must declare the full-source denominator 57027.
5. `FB/operations/run_actual_sunday.py:581` - `if (not (full or pilot) or manifest.get('source_records') != 57027 ...)` -> `raise ValueError('independently pinned Sunday prefix manifest covering the requested cycles required')` - **`encoding_options()` gate on the prefix manifest** (also carries the `19`/`2`+`scheduled_cycles 19` shape, see A3).
6. `FB/operations/run_actual_sunday_compact_source.py:105` - `receipt['source_records_expected']!=57027` - **the compact-source subclass's copy of the same prefix() refusal** (deliberately verbatim; `tests/test_run_actual_sunday_compact_source.py` is a drift-guard holding this method to the lawful text modulo the anchor read). Must change in lock-step with site 4.
7. `FB/operations/build_remaining_sunday_prefixes.py:221-225` - `if (ingestion['record_count'] != 57027 or completion['record_count'] != 57027 or outer['source_records'] != 57027 or outer['steps'] != 19 or outer['source_completion'] != completion or len(schedule['steps']) != 19 or outer['schedule_file_sha256'] != host['schedule']['sha256']): raise ValueError('full Sunday source and full nineteen-cutoff schedule required')` - **the prefix builder's input validation** (`validate_inputs`), runs before any source DB is opened.
8. `FB/operations/build_remaining_sunday_prefixes.py:255` - `if cursors != sorted(set(cursors)) or cursors[0] != 3261 or cursors[-1] >= 57027: raise ValueError('original ordered Sunday cutoffs required')` - **a hard-pinned first cutoff cursor (`3261`) and a record-count upper bound**. `3261` is an extra Sunday literal the capability map does not name as a separate value; it is the first schedule step's `through_cursor`.
9. `FB/operations/build_remaining_sunday_prefixes.py:391` - `witnesses=[witness(first_path)] + results, prefixes=cycles, source_records=57027,` - **the count written INTO the emitted prefix manifest** (`full19-prefix-witnesses.json` / `prefix-batch-02.json`), which sites 5 and 12 then read back.
10. `FB/operations/run_journal_stack.py:77-78` - `scope_hash=EXPECTED['scope_hash'],record_count=57027,member_counts=(57027,), group_count=43569,` - **the expected `BOSS_SOURCE_CONFORMANCE_V1` completion dict**; `if asdict(result.completion)!=expected ... raise ValueError('final conformance result differs')` (l.81-82). Note `member_counts=(57027,)` is a ONE-MEMBER tuple: the trading day has two members. `43569` (F_LAST group count) is a further Sunday literal the map does not list.
11. `FB/operations/run_journal_stack.py:85` - `gate_authority=False,model_calls=0,source_records=57027,journal_entries=114054,` - **the receipt this job writes** (`FRANKIE_COMBINED_JOURNAL_EXECUTION_V1`), consumed downstream as the ingest gate.
12. `FB/operations/seal_final_prelaunch_candidate.py:63` - `if ingestion.get('record_count')!=57027:raise ValueError('complete Sunday ingestion receipt required')` - **the pre-launch seal's ingestion gate**.
13. `FB/operations/seal_final_prelaunch_candidate.py:64` - `if (prefixes.get('schema')!='FRANKIE_FULL_SUNDAY_PREFIX_WITNESSES_V1' or prefixes.get('prefixes')!=19 or prefixes.get('source_records')!=57027 or len(prefixes.get('witnesses',[]))!=19):raise ValueError('complete nineteen-prefix manifest required')` - **the seal's prefix-manifest gate** (schema string + 19 + 57027 + 19, four gates in one line).
14. `FB/operations/parallel_source/verify_snapshot.py:26` - `EXPECTED = dict(journal_count=114054, next_cursor=57027, sha256='750dbb3c...', state_hash='d46ec933...', scope_hash='7460b519...', journal_hash='d8de0394...', source_prefix_hash='39270e89...')` - **the module-level terminal-identity constant**, imported by `run_journal_stack.py:16`. Single place where all seven Sunday terminal hashes live; everything in run_journal_stack and verify_snapshot resolves through it.
15. `FB/operations/parallel_source/verify_snapshot.py:224-229` - `record_count=57027, member_counts=(57027,), group_count=43569, ...; if asdict(completion) != expected_completion: raise ValueError('verified completion differs from full Sunday terminal identity')` - **the independent verifier's completion gate** (twin of site 10).

### A2. The `114054` journal-entry count (2 entries per record)

16. `FB/operations/parallel_source/verify_snapshot.py:26` - `journal_count=114054` (in `EXPECTED`) - see site 14. Also enforced at `verify_snapshot.py:215-219` (`state['journal_count'] != EXPECTED['journal_count'] -> 'terminal state differs from checkpoint receipt'`) and at `run_journal_stack.py:57-60` (`state['journal_count']!=EXPECTED['journal_count'] -> 'terminal bindings differ'`).
17. `FB/operations/run_journal_stack.py:69` - `emit(dict(phase='cpu_dedication', ..., entries=0, total=114054, percent=0.0))` - **progress denominator** (cosmetic, but wrong-day progress).
18. `FB/operations/run_journal_stack.py:97` - `emit(dict(phase='verified',entries=114054,total=114054,percent=100.0,...))` - **terminal progress line**.
19. `FB/operations/run_journal_stack.py:85` - `journal_entries=114054` - receipt field (same line as site 11).
20. `FB/journal_stack_execution.py:72` (comment, load-bearing for the box math) - `# by MAX_ROWS entries, and its bodies by MAX_BYTES. The Sunday's 114,054 entries need 96 per box to` / l.73 `# make 1,189 ...` - **the documented derivation of the box standard**; also l.77-79 note "the first run's compact_sha256 19603159... no longer reproduces".

### A3. `19` as a step/prefix/cycle count

21. `FB/verified_sunday_schedule.py:29-30` - `if type(steps) is not list or len(steps)!=19: raise ValueError('nineteen original cutoffs required')` - **the schedule verifier's step-count refusal**. The single choke point: both `run_actual_sunday.source()` (l.365-366) and `build_remaining_sunday_prefixes.validate_inputs` (l.226-227) call `verified_schedule()`.
22. `FB/verified_sunday_schedule.py:26-27` - `if result['schema']!='BOSS_SUNDAY_CAUSAL_CYCLE_SCHEDULE_V1': raise ValueError('unsupported schedule schema')` - **the schedule schema name carries "SUNDAY"**.
23. `FB/verified_sunday_schedule.py:35` - `STEP if index<18 else TERMINAL` - **the 19-step shape hard-coded in the field-order restoration** (step 18 is the last; its `feedback_available_through` has the TERMINAL shape, not the STEP shape).
24. `FB/sunday_schedule.py:24-25` - `if len(indices) != 19 or indices != sorted(set(indices)): raise ValueError('complete retained nineteen-cutoff roster required')` - **the schedule BUILDER's cutoff-roster refusal** (build_schedule reads the principal's `invocation_cutoffs`).
25. `FB/sunday_schedule.py:71-75` - `result = dict(schema='BOSS_SUNDAY_CAUSAL_CYCLE_SCHEDULE_V1', ..., model_context_rows=model_context_rows, source_dates_required=1, feedback_lag='next retained cutoff')` - **`source_dates_required=1` is a hard-coded literal in the emitted schedule** (this is the "one source date" the trading day breaks: the Monday day needs 2). `model_context_rows` is correctly a parameter, never a literal (l.17-18 refuses a non-positive value).
26. `FB/sunday_execution.py:208-210` - `if len(self.steps)!=19 or any(a['as_of']>=b['as_of'] or a['through_cursor']>=b['through_cursor'] for a,b in zip(self.steps,self.steps[1:])): raise ValueError('complete increasing 19-cycle runtime schedule required')` - **the runtime driver's schedule refusal** at `SundayExecution.__init__`.
27. `FB/sunday_execution.py:221` - `if type(index) is not int or not 0<=index<19:raise ValueError('valid Sunday cycle index required')` - **per-cycle index bound** in `run_cycle`.
28. `FB/sunday_execution.py:331,333` - `async def run_remaining(self, *, cycles=19):` / `if type(cycles) is not int or not 1 <= cycles <= 19:` - **loop bound on the cycle run**.
29. `FB/source_contract_runtime.py:21-22` - `if body.get('schema')!='FRANKIE_OWN_SOURCE_CONTRACT_V1' or len(body.get('cycles',[]))!=19: raise ValueError('complete principal-authored 19-cycle source contract required')` - **the principal source contract must contain exactly 19 cycles** (the contract file is 2.5 MB of authored cycles; a new day needs a new contract).
30. `FB/frankie_principal_adapter.py:415-416` - `if cycle_index is not None and (type(cycle_index) is not int or not 0 <= cycle_index < 19): raise ValueError('valid Sunday cycle index required for the calculation pin')` - **adapter constructor bound**. Also `frankie_principal_adapter.py:98` - `raise ValueError('cycle calculation pin required: valid Sunday cycle index required')`.
31. `FB/operations/run_actual_sunday.py:283` - `request_id in {f"{self.config['run_id']}-cycle-{index:02d}" for index in range(19)}` - **the SSM credential trigger's request-identity allowlist**: only 19 request ids can ever unlock the key. A 20th cycle cannot read the credential.
32. `FB/operations/run_actual_sunday.py:122` - `for index in range(19):` (in `await_recorded_principal`) - **the scan for the unique retained principal request** across `execution/cycle-NN/principal/session-request.json`; `if len(matches)!=1: raise ValueError('unique retained principal request required')`.
33. `FB/operations/run_actual_sunday.py:771` - `self.progress('input_inventory',completed=binding['cycle_index'],total=19,unit='steps')` - **progress denominator** in `runtime()`.
34. `FB/operations/run_actual_sunday.py:945-946` - `probe.advance('complete',completed=len(result),total=19,unit='steps')` / `print(json.dumps(dict(status='all_nineteen_cycles_complete',cycles=len(result))))` - **the terminal status string the pipeline parses**.
35. `FB/operations/run_actual_sunday.py:577-580` - `full = manifest.get('schema') == 'FRANKIE_FULL_SUNDAY_PREFIX_WITNESSES_V1' and manifest.get('prefixes') == 19` / `pilot = (... 'FRANKIE_SUNDAY_PREFIX_BATCH_V1' and manifest.get('prefixes') == 2 and manifest.get('scheduled_cycles') == 19 and getattr(self, 'cycle_limit', 19) <= 2)` - **the two accepted prefix-manifest shapes** (full 19, or the 2-cycle pilot that still declares 19 scheduled).
36. `FB/operations/build_remaining_sunday_prefixes.py:331-333` - `def main(configuration_path, *, cycles=19):` / `if type(cycles) is not int or cycles not in (2,19): raise ValueError('prefix batch must contain two or nineteen cycles')` - **the builder accepts only 2 or 19**, nothing else.
37. `FB/operations/build_remaining_sunday_prefixes.py:390,395,396,406` - `schema=('FRANKIE_FULL_SUNDAY_PREFIX_WITNESSES_V1' if cycles == 19 else 'FRANKIE_SUNDAY_PREFIX_BATCH_V1')` / `if cycles != 19: result['scheduled_cycles'] = 19` / `final = output / ('full19-prefix-witnesses.json' if cycles == 19 else 'prefix-batch-02.json')` / `parser.add_argument('--cycles',type=int,choices=(2,19),default=19)` - **schema name, scheduled_cycles literal, and the OUTPUT FILENAME `full19-prefix-witnesses.json`**.
38. `FB/operations/day_pipeline.py:72,77` - `cycle_limit=19` default / `if type(cycle_limit) is not int or not 1 <= cycle_limit <= 19: raise ValueError('cycle_limit must be from 1 through 19')` - **pipeline cycle bound**.
39. `FB/operations/day_pipeline.py:180` - `if stage == 'schedule-prefixes' and gate['prefix_count'] < min(self.c.get('minimum_prefixes', 19), self.cycle_limit): raise StageRefused('fewer prefixes than the day requires')` - **the prefix-count stage gate** (default 19; also declared as `"minimum_prefixes": 19` in `FB/operations/day_pipeline.configuration.json`).
40. `FB/operations/day_pipeline.py:237-241` - `if (value.get('day') != self.day or value.get('cycles_total') != 19 or value.get('cycles_completed') != self.cycle_limit or value.get('requested_cycles') != self.cycle_limit or self.cycle_limit == 19): raise StageRefused('partial cycles receipt differs from the requested batch')` - **the partial-batch receipt gate**, and the emitted filename `04-cycles-batch-{self.cycle_limit:02d}.json` at l.242.
41. `FB/operations/day_pipeline.py:355` / `FB/operations/run_actual_sunday_compact_source.py:208` / `FB/operations/run_actual_sunday_classroom.py:278` - `parser.add_argument('--cycles', type=int, choices=range(1, 20), default=19)` - **CLI bound, three copies**.
42. `FB/operations/run_actual_sunday_classroom.py:261,316` - `return await runner.run_remaining(cycles=getattr(self, 'cycle_limit', 19))` / `status=("all_nineteen_cycles_complete" if args.cycles == 19 ...)` - classroom runner's copies.
43. `FB/operations/benchmark_native_learner_direct.py:198` - `if len(steps)!=19: raise ValueError('complete 19-step schedule required')` - **benchmark harness step gate** (NOT in the capability map).
44. `deploy/aws/host/day_schedule_prefixes.ps1:16` - `if ([int]$CycleLimit -ne 2 -and [int]$CycleLimit -ne 19) { throw 'Prefix batch must be two or nineteen cycles' }` - **host-side stage-4 refusal** (NOT in the map).
45. `deploy/aws/host/frankie_host_rebuild_prefix_batch.ps1:29` - `if ([int]$CycleLimit -ne 2) { throw 'this rebuild covers the two-cycle batch only (prefix-batch-02.json)' }` - **the re-mint script is hard-bound to the 2-cycle batch**.

### A4. `1189` / the box standard

46. `FB/box_standard.py:13` - `TARGET_BOXES = 1189` - **the one definition**; `partition_entries_for(count, *, target=TARGET_BOXES, ceiling=MAX_ROWS)` at l.16-20 returns `max(1, min(ceiling, -(-count // target)))`. NOT Sunday-bound in mechanism (it is derived from `count`), but its docstring l.3-4 is written around 114,054 -> 96 rows/box -> 1,189 boxes. For the trading day `partition_entries_for(2*2_032_203)` = 4064/box clamped by MAX_ROWS.
47. `FB/journal_stack_execution.py:64-80` (comment block) + l.80 `from box_standard import TARGET_BOXES, partition_entries_for` and l.88-89 `if partition_entries is None: partition_entries = partition_entries_for(expected_count)` - **the re-export and the derivation site** for the journal-stack reader.
48. `FB/compact_build_journal.py:64` - docstring `TARGET_BOXES = 1189 for every day we ingest` on `__init__(self, path, *, block_bytes=MAX_BYTES // 2, workers=0, block_rows=MAX_ROWS)` - **the writer's box-cut rule**.
49. `FB/operations/ingest_block_sources.py:162-169` - `if block_rows is None: block_rows = partition_entries_for(2 * total)` / `standard='box_standard.TARGET_BOXES 1189: rows per box = partition_entries_for(2 x declared records), bytes per box = the format ceiling'` - **the ingest tool already derives box rows from the DECLARED total** (`total = sum(member.mbo_records for member in scope.members)`). This is already trading-day-correct; nothing to change.

### A5. `20211003` / one-UTC-day / "full Sunday" strings

50. `FB/source_contract_runtime.py:124` - `agent={'run_id':identity['run_id'],'arm':identity['arm'],'source_day':'20211003', ...}` - **the literal source day stamped into `preparation-pins.json`** (`FRANKIE_BOSS_PREPARATION_PINS_V1`). Retained pins are compared byte-for-byte at l.142-143 (`raise ValueError('retained preparation pins differ')`), so this literal is load-bearing for restart idempotence.
51. `FB/source_contract_runtime.py:162` - `protected_files={'Memory A':witnesses['FROZEN_MEMORY_A_20211003.json']}` - **a filename key**: the retained-witness roster must contain a file named for the Sunday date.
52. `FB/source_contract_runtime.py:157-158` - `witnesses['sunday_spawn_prompt.md']` - **filename key** in the same roster.
53. `FB/frankie_principal_adapter.py:657-660` - the prompt prefix literal `"Sunday 2021-10-03 is the sole source and run day. No separate source day or October 1 prerequisite applies. ... Preserve frozen pre-Sunday Memory A ... Its multi-day sequencing is overridden by this current single-day instruction."` - **the text handed to the principal session**; this is the day identity the model itself reads.
54. `FB/frankie_principal_adapter.py:773` - `'is Sunday only and requires no separate source day. Preserve Memory A. ...'` - **the instruction string in the `FRANKIE_BOSS_SESSION_REQUEST_V1` request body** (hashed into the durable session-request; changing it changes the request identity).
55. `FB/frankie_principal_adapter.py:317,327,345,428` - `"""Verify historical bytes directly; never rebuild from post-Sunday checkout."""` / `raise ValueError('only the frozen pre-Sunday Memory A is admissible')` / `MEMORY_A_ATTESTATION = ('Greg Davis, 2026-09-17: the frozen pre-Sunday Memory A seed is declared VALID as served. ... no validation day or separate source day exists or is required.')` / `raise ValueError('explicit pinned pre-Sunday knowledge receipt and bundle required')` - **the Memory-A admission chain, all phrased "pre-Sunday"**. Mechanically date-free (it pins `FROZEN_MEMORY_SHA256` + `bytes == 166700`), so a trading-day rerun can keep it; only the wording is Sunday.
56. `FB/raw_mbo_source_manifest.py:14-18` - `EXPECTED_ROSTER = (("20211001","WARMUP_DEVELOPMENT"),("20211003","WARMUP_DEVELOPMENT"),("20211004","HELD_OUT_BLIND"),("20211005","HELD_OUT_BLIND"))` and `EXPECTED_NAMES = tuple(f"glbx-mdp3-{date}.mbo.dbn.zst" ...)` - **a four-date UTC-day roster with a blind/warmup split**, i.e. the OLD "break the days up" model. `selected_source_scope.py` docstring explicitly says it bypasses this ("no four-date or warmup gate"), but `manifest_hash` from this module is still what hashes both the Sunday and the block manifests. NOT in the capability map.
57. `FB/block_source_scope.py:41` - `raise ValueError('block manifest members must carry exactly the Sunday member fields, in replay order')` - **the block binder's member-shape refusal**, phrased against "the Sunday member fields". This module is already the multi-member replacement for `selected_source_scope` (checks `member_seams_close_groups` and `halt_boundaries_close_groups`, sums `mbo_records` against `total_mbo_records`). Gate string only.
58. `FB/operations/ingest_block_sources.py:360-361,385,390` - `parser.add_argument('--sunday', action='store_true', help='the Sunday single-source scope instead of a block')` / `--source-path` / `raise SystemExit('--sunday requires --source-path')` / `source_label = dict(scope='sunday', ...)` - **the CLI's Sunday-only branch**, which builds `source_manifest()`/`source_scope()` from `selected_source_scope`. The `--manifest`+`--sources-dir` branch (l.392-400) is the trading-day path and reads `manifest['halt_utc_hour']`; `--session-policy cme_trading_day` already exists.
59. `FB/operations/day_pipeline.py:196-209` - `"""An ingest receipt is about THIS day only if it reduced the records this day staged."""` ... `expected = self.receipt('stage-sources')['gate']['records']` ... `raise StageRefused(f'ingest receipt reduced {count} records; {self.day} staged {expected}. ...')` - **the ingest/stage reconciliation is per-DAY (`self.day`, one YYYYMMDD)**; `__init__` l.74-75 `if not self.day.isdigit() or len(self.day) != 8: raise ValueError('day must be YYYYMMDD')`. The run directory (`runs/<DAY>/`, l.76), the manifest filename (`BLOCK_{self.day}_SOURCE_MANIFEST.json`, l.147), the upload prefix (l.153) and the snapshot label (l.154) are all one UTC day. This is the pipeline-level UTC-day split; the map names only l.237.
60. `FB/operations/build_remaining_sunday_prefixes.py:225,256,365,390` - `'full Sunday source and full nineteen-cutoff schedule required'` / `'original ordered Sunday cutoffs required'` / `schema='FRANKIE_REMAINING_SUNDAY_PREFIXES_V1'` / `'FRANKIE_FULL_SUNDAY_PREFIX_WITNESSES_V1'` - **refusal strings + two schema names carrying SUNDAY**.
61. `FB/operations/parallel_source/verify_snapshot.py:1,229` - `"""Independent Sunday snapshot verification. ..."""` / `raise ValueError('verified completion differs from full Sunday terminal identity')`.
62. `FB/operations/run_journal_stack.py:95` - `model_input_reduction='Sunday host remains configured for stacked_v1; no inference in this job'` - receipt string.
63. `FB/operations/seal_final_prelaunch_candidate.py:63` - `'complete Sunday ingestion receipt required'`; `:8` - `DEFAULT_HOST=Path(__file__).with_name('run_actual_sunday.py')`.
64. `FB/sunday_execution.py:48,61,229,235,265` - `'retained Sunday execution evidence changed'` / `'noncanonical Sunday execution evidence'` / `'complete the preceding Sunday cycle before advancing'` / `'explicit SundayRuntime factory result required'` / `schema='FRANKIE_SUNDAY_REQUEST_PLAN_V1'` - gate strings + one schema.
65. `FB/operations/restore_sunday_working_tree_identity.py:27-28,36,74,99,157,224,226` and `FB/operations/audit_sunday_restoration_manifest.py:22,39,70-71,127` - `FRANKIE_SUNDAY_*` schema names and Sunday refusal strings (restore/audit tooling; not on the rerun path but will read stale).
66. **Filenames themselves**: `run_actual_sunday.py`, `run_actual_sunday_classroom.py`, `run_actual_sunday_compact_source.py`, `run_actual_sunday_ec2.py`, `build_remaining_sunday_prefixes.py`, `restore_sunday_set_on_host.py`, `upload_sunday_restore_set.py`, `sunday_execution.py`, `sunday_native_runtime.py`, `sunday_schedule.py`, `verified_sunday_schedule.py`, `SPEC-sunday-runtime.md`, `SUNDAY_EXECUTION_BOUNDARY.md`, dir `sunday_20260915_package/`. Renaming any of them breaks the **sha256 code pins** (see A7) and `restore_sunday_working_tree_identity.py:36`, which lists `research/kalshi/frankie_boss/sunday_native_runtime.py` by path.

### A6. The box driver's one-UTC-day source object

67. `/home/user/Markets/deploy/aws/box/frankie_box_bedrock.py:131-142` - `def source_object(container, day):` ... `if not (len(day) == 8 and day.isdigit() and day.startswith('20')): raise ValueError(f'the source day must be 20YYMMDD, not {day!r}')` ... `return f'journal:{day}:{path}', str(sha)` - **the driver's source object is ONE 20YYMMDD UTC day**, and the docstring states the driver parses the day back out (`native_replay_driver._source_day` reads the first `20YYMMDD` in the object name). A trading day spanning 20211003+20211004 has no single such token; the natural form is the TRADE DATE (`20211004`) with the container path following, which the current validator already accepts (it validates shape, not membership).
68. `deploy/aws/box/frankie_box_bedrock.py:145-158` - `driver_records(records, container, day)`: `stamped['source_dbn_object'] = path; stamped['source_dbn_sha256'] = str(sha)` - **every row the box sees carries the one-day object + the container's sha256**; the driver refuses a record without it. `identity()` l.170-179 sets `source_manifest_hash=str(container['sha256'])` and `total_mbo_records=int(count)` - **the container's sha256 IS the manifest hash for the box, and the count is passed in, not literal** (already trading-day-ready).
69. `deploy/aws/box/*` - `frankie_box_boss_session.py:34,1184,1682,1936`, `frankie_box_teach.py:226`, `frankie_box_heartbeat.py:12,70`, `frankie_box_session.sh:7,15`, `frankie_box_push_response.sh:6,10`, `frankie_box_install_agent_backend.sh:21`, `frankie_box_probe_checkouts_and_role.sh:21` - **`20211003` as an argparse default, an S3 key prefix (`host-deliveries/20211003/...`), and inside the prompt text handed to the box model** ("cycle {cycle} of the 20211003 two-cycle run"). NOT in the capability map; these are the box-side day literals.
70. `.github/workflows/frankie_host_*.yml` and `frankie_box_fetch_response.yml` - `default: '20211003'` in ~14 workflow inputs (`frankie_host_advance`, `_restore_mapping_index`, `_supersede_readiness`, `_supersede_cycle`, `_cycle_report`, `_cycle_binding_probe`, `_record_principal_response`, `_cycle_status`, `_supersede_principal_request`, `_declare_identity_supersede`, `_supersede_code_bound_state`, `_supersede_classroom_package`, `_binding_diff`, `frankie_box_fetch_response`) plus `frankie_host_rebuild_prefix_batch.yml:17`. Also `.github/workflows/frankie_boss_source_stage.yml:30-35` hard-codes the S3 key `.../20211001_20211101/glbx-mdp3-20211003.mbo.dbn.zst`. Also `deploy/aws/host/frankie_host_diag.ps1:4` `$day = 'C:/Codex/Frankie-BOSS-20260919/days/20211003'` and `deploy/aws/build_readiness_delivery.py:25` `HOST_CONFIGURATION = 'C:/.../days/20211003/actual-host-configuration.json'`.
71. `.github/frankie-journal-stack-request.json:4-5` - `"records": 57027, "entries": 114054` - **the committed journal-stack request pins the Sunday counts**. NOT in the capability map.

### A7. Code-sha256 pins that make any rename/edit a refusal
72. `FB/operations/build_remaining_sunday_prefixes.py:314-315` (seed sidecar check) and `:370-377` (binding) - `script_sha256=sha(__file__)`, `copier_sha256=sha(snapshot.__file__)`, `runtime_code_sha256=sha(sunday_native_runtime.__file__)`, `selection_code_sha256=sha(context_session.__file__)`, `compact_copier_sha256`, `full_reader_sha256` - **six code pins written into `remaining-prefix-binding.json`**.
73. `FB/operations/run_actual_sunday.py:595-598` - `code=Path(self.repo)/'research/kalshi/frankie_boss'; selection_code=sha(code/'context_session.py'); runtime_code=sha(code/'sunday_native_runtime.py')` then `if (batch['context_selection']!=dict(entity=list(self.context.entity),t_ctx=self.context.t_ctx, runtime_code_sha256=runtime_code, selection_code_sha256=selection_code) ...): raise ValueError('prefix seed differs from verified current snapshot/context selection')` - **this is "the runner problem"**: the host re-hashes the checkout and refuses when the binding's pins are stale.
74. `FB/operations/run_actual_sunday.py:256-261` - `actual=subprocess.check_output(['git','rev-parse','HEAD'...]); if actual!=self.host['boss_commit']: raise ValueError('explicit current BOSS commit required')` + `git diff --exit-code HEAD -- research/kalshi/frankie_boss research/refrag` + `self.code={... for p in sorted((self.repo/root).rglob('*.py')) if 'tests' not in p.parts}` - **the whole package is hashed into the training identity** (`code_hash` at `_training()` l.484), so ANY edit in this map changes `code_hash` and invalidates retained preparations. Same check at `seal_final_prelaunch_candidate.py:49-54`.

---

## B. DATA SHAPES

### B1. The verified schedule file

**Validator** - `FB/verified_sunday_schedule.py::verified_schedule(value, *, expected_digest)`:
- `TOP` (l.10-12, the hashed body, in producer order): `('schema','cutoff_file_sha256','mapping_index_sha256','steps','terminal_delivery','first_observed_trade_candidate','anchor_authorship','model_context_rows','source_dates_required','feedback_lag')`.
- File keys = `TOP + ('schedule_sha256',)` exactly - `_ordered` (l.19-22) refuses any extra or missing key: `if type(value) is not dict or set(value)!=set(keys): raise ValueError('schedule V1 fields differ')`. **Adding a trading-day field (halt, session, two dates) fails here unless TOP changes.**
- `STEP` = `('group_index','groups_delivered','through_cursor','records_delivered','as_of','source_as_of','source_hash')`; each step also has `feedback_available_through`, shaped `STEP` for indexes 0-17 and `TERMINAL` for index 18.
- `TERMINAL` = `('groups_delivered','records_delivered','through_cursor','as_of','source_as_of','source_hash')`.
- `TRADE` (for `first_observed_trade_candidate`, may be `None`) = `('cursor','ts_event_ns','ts_recv_ns','price_raw','evidence_hash','source_prefix_hash')`.
- **Digest**: `digest = sha256(canonical_bytes(pack({key:result[key] for key in TOP})))`; refuses unless `digest == result['schedule_sha256'] == expected_digest` (l.41-44, `'completed logical schedule identity differs'`). `expected_digest` comes from the schedule RECEIPT's `schedule_sha256`.
- **`model_context_rows`**: read but NOT range-checked here; the producer (`sunday_schedule.build_schedule`, l.17-18) refuses non-int/<1; the consumers re-check - `build_remaining_sunday_prefixes.py:339-340` `t_ctx=schedule['model_context_rows'] ... if type(t_ctx) is not int or t_ctx<1: raise ValueError('the verified schedule must declare a positive model_context_rows')`, and `run_actual_sunday.py:480` `if self.schedule is None: raise ValueError('the verified schedule (model_context_rows) is required before training; verify the sources first')`.
- **`source_dates_required`**: read into TOP and hashed, but **no code compares it to anything** (grep: only `verified_sunday_schedule.py:12` and `sunday_schedule.py:75`). It is a declared-and-hashed field, not an active gate - so setting it to `2` for the trading day only changes `schedule_sha256`, it triggers no refusal by itself.
- **`first_observed_trade_candidate`**: shape-checked only if non-`None`; no value gate.
- **Cutoffs**: enforced indirectly - `build_remaining_sunday_prefixes.py:254-256` requires the 19 `through_cursor`s strictly increasing with `cursors[0]==3261` and `cursors[-1] < 57027`; `sunday_execution.py:208-209` requires both `as_of` and `through_cursor` strictly increasing across the 19 steps; `sunday_schedule.py:66-69` requires each step's feedback `as_of` strictly later.

**Where the cycle-0 schedule file lives**:
`/home/user/Markets/research/kalshi/frankie_boss/sunday_20260915_package/FB/full-causal-schedule-resumed-20260915/schedule.json` (10,678 bytes, file sha256 `97da6c589cb64ffb6ff4ba692a1344ad9f16773b10e3ed8783e0ad4bf1f93b2e`), with its receipt beside it at `.../receipt.json` (sha256 `c0ffd954...`).

Top-level keys and values (measured):
```
schema                        = 'BOSS_SUNDAY_CAUSAL_CYCLE_SCHEDULE_V1'
cutoff_file_sha256            = '4b869d1f44a97a08196cd428ac10a34f36f3f55d70f22d6e50116cc7be9f80d9'
mapping_index_sha256          = 'f62c522dcc00a4d3e1caeac7a8e1e4e534a437ef53be200e991508236c027ca6'
steps                         = list of 19
terminal_delivery             = {groups_delivered 43569, records_delivered 57027, through_cursor 57026,
                                 as_of 1633305596372071705, source_as_of 1633305596371955033,
                                 source_hash '39270e89...'}
first_observed_trade_candidate= {cursor 447, ts_event_ns 1633298400000000000, ts_recv_ns 1633298400295735538,
                                 price_raw 5628000000, evidence_hash '24602ab2...', source_prefix_hash '17e30cfc...'}
anchor_authorship             = 'candidate evidence only; principal must certify interval convention'
model_context_rows            = 4096              <-- the declared row window (Greg's number)
source_dates_required         = 1                 <-- the one-date declaration
feedback_lag                  = 'next retained cutoff'
schedule_sha256               = 'f6922f7a4b93b44394c6683e3d7c45782f27e250c81987bd54414fb124c60e42'
```
The 19 `through_cursor`s: `3261, 6053, 9417, 12696, 15692, 18819, 21782, 24641, 27395, 30336, 33192, 35947, 39029, 41974, 44963, 47945, 51004, 53962, 56758`. `steps[0]` = `{group_index 2281, groups_delivered 2282, through_cursor 3261, records_delivered 3262, as_of 1633298413318097271, source_as_of 1633298413317923251, source_hash 'e947260436...', feedback_available_through {...through_cursor 6053...}}`. First `as_of` 1633298413... = 2021-10-03 22:00:13Z (the 18:00 ET open), terminal 1633305596... = 2021-10-04 00:00:0xZ - i.e. **the whole 19-cycle schedule covers only the first ~2 hours of the trading day**; a 23-hour day is many more cycles (matches capability-map assumption 4).

**Schedule receipt** (`.../receipt.json`, the `outer` in the gates): keys `schema='FULL19_SUNDAY_SCHEDULE_EXECUTION_V1'`, `steps=19`, `source_records=57027`, `verified_records=57027`, `verified_terminal_prefix='39270e89...'`, `schedule_sha256`, `schedule_file_sha256='97da6c58...'`, `cutoffs_sha256`, `index_sha256`, `source_checkpoint_sha256='750dbb3c...'`, `source_checkpoint_state_hash='d46ec933...'`, `source_completion` (full `BOSS_SOURCE_CONFORMANCE_V1`: `record_count 57027`, `member_counts [57027]`, `group_count 43569`, `journal_count 114054`, `journal_hash 'd8de0394...'`, `scope_hash '7460b519...'`, `scope_kind 'RESULT_BEARING'`, `source_prefix_hash '39270e89...'`, `builder_state_hash 'd46ec933...'`), `reader_code_sha256`, `view_code_sha256`, `view_evidence_class='READ_ONLY_COMPLETED_SOURCE_SCHEDULE_VIEW'`, `model_forwards=0`, `principal_calls=0`.
**Note:** the string `FULL19_SUNDAY_SCHEDULE_EXECUTION_V1` appears in **no code in the repo** - only in this retained receipt. The producer script is gone; the consumers read `outer['steps']`/`outer['source_records']` positionally, never the schema name. The read-only view helper that built it is `FB/completed_schedule_view.py` (`open_completed_schedule_view`), whose l.60-61 refuses `chain.next_cursor != sum(member.mbo_records for member in scope.members)` - already member-count-general.

### B2. The prefix binding and a prefix seed

**Batch binding** - `sunday_20260915_package/FB/actual-prefixes/remaining-prefix-binding.json`, schema `FRANKIE_REMAINING_SUNDAY_PREFIXES_V1`, written by `build_remaining_sunday_prefixes.py:365-383` (idempotent: byte-identical or `'retained prefix batch identity changed'`).

| field | pins |
|---|---|
| `script_sha256` `d6c74238...` | **CODE** - `operations/build_remaining_sunday_prefixes.py` |
| `copier_sha256` `1a982ba1...` | **CODE** - `journal_prefix_snapshot.py` |
| `compact_copier_sha256` `858a7afd...` | **CODE** - `compact_journal_snapshot.py` |
| `full_reader_sha256` `bfa6e787...` | **CODE** - `frankie_journal_reader.py` |
| `context_selection.runtime_code_sha256` `40ace66b...` | **CODE** - `sunday_native_runtime.py` |
| `context_selection.selection_code_sha256` `7e5550c1...` | **CODE** - `context_session.py` |
| `context_selection.entity` `[1, 111313]`, `.t_ctx` `4096` | the context selection (t_ctx = the schedule's `model_context_rows`) |
| `compact_journal` `{path, bytes 569667584, sha256 19603159548b1e443a3565f8c999543981c43c23c80fd511c11e760f633b260f}` | **THE CONTAINER** (the compact journal) |
| `source_journal_sha256` `181467d1...` | the raw `source.sqlite` bytes |
| `source_count` `114054`, `source_head_hash` `d8de0394...` | **THE SNAPSHOT/JOURNAL identity** (count + head) |
| `ingestion_receipt`, `schedule_receipt`, `schedule`, `source_lineage` (each `{path,bytes,sha256}`) | the four-witness quartet; re-checked at `run_actual_sunday.py:590-591` and `seal_final_prelaunch_candidate.py:78-79` |
| `preserved_prefix00` `{path,bytes 485,sha256 1ac352dc...}` | cycle 0's retained witness (never rebuilt) |
| `data_workers` `48`, `model_calls` `0`, `source_replays` `0` | runtime declaration |

**Prefix seed** - `sunday_20260915_package/FB/actual-prefixes/prefix-01-packet-seed.json`, schema `FRANKIE_VERIFIED_CONTEXT_PREFIX_SEED_V1`. Keys (all 22):
```
schema, selection='TOP_T_CTX_BY_RECEIVE_TIME_AND_CURSOR', cycle_index=1,
t_ctx=4096, entity=[1,111313],
context_cursors=[1958...6053]  (list of 4096 ints),
context_cursors_sha256='8549f6f8...',
derivable=true, reason=null,
seed={next_cursor 1958, previous_prefix_hash '37a3a408...', scope_genesis_hash '7460b519...'},
through_cursor=6053, verified_records=6054,
as_of=1633298449136124134, source_as_of=1633298449135867821,
source_prefix_hash='0b75276d...', source_scope_hash='7460b519...',
snapshot_sha256='6873366e...', snapshot_receipt_sha256='f5486727...',
batch_binding_sha256='0d700fc3...',
selection_code_sha256='7e5550c1...', runtime_code_sha256='40ace66b...'
```
- **pins code**: `selection_code_sha256` (context_session.py), `runtime_code_sha256` (sunday_native_runtime.py) - re-verified at `build_remaining_sunday_prefixes.py:314-315` and `run_actual_sunday.py:596-608`.
- **pins the snapshot/container**: `snapshot_sha256` (the prefix `.sqlite`), `snapshot_receipt_sha256`, `source_scope_hash` (-> the 57027 manifest), `source_prefix_hash`, `batch_binding_sha256` (-> the binding, -> the compact container).
- **derivability rule** (`run_actual_sunday.py:627-642`): the 4096 cursors must be contiguous and end exactly at `through_cursor`, else `reason ? {'no_entity_context','noncontiguous_source_cursors','context_omits_terminal_cursor'}` and `seed` must be `None`.

**Manifest** - `full19-prefix-witnesses.json`: `{schema='FRANKIE_FULL_SUNDAY_PREFIX_WITNESSES_V1', prefixes=19, source_records=57027, witnesses=[19 x {path,bytes,sha256}], prefix_seed_witnesses={'1'...'18' -> witness}, binding={path,bytes,sha256}, model_calls=0, source_replays=0}`. Note: 19 witnesses but only 18 seed witnesses (cycle 0 begins at genesis and has `prefix_seed=None`, `run_actual_sunday.py:575`).

### B3. `run_actual_sunday.py` - source() / _training() / runtime() flow

**`runtime(binding, cycle_directory, retained_plan)` (l.770-877)** is the per-cycle entry called by `SundayExecution`. Order: `source()` -> `prefix()` -> `_training()` (once) -> tokenizer admission -> prepare/admit -> SSM trigger -> `SundayRuntime`.

**`source()` (l.340-389) - how it locates everything:**
- Everything comes from the **configuration**, nothing is discovered. `self.config` = the host configuration JSON; `self.host = configuration['host_runtime']`.
- l.342-343 verifies the seven config witnesses (`memory, contract, mapping, retained_witnesses, delivery_receipt, calculation_result, source_manifest`) by `{path,sha256}`.
- l.344: `source=Path(self.config['source_directory']); schedule=Path(self.config['schedule_directory'])`; a `failure.json` in either refuses (l.345-346).
- **Receipts**: `receipt=verified_json(self.host['ingestion_receipt'])`, `outer=verified_json(self.host['schedule_receipt'])`; l.348 requires the ingestion receipt to BE `source/ingestion-receipt.json`.
- **Counts gate** l.351-353 (site 3).
- **Checkpoint**: `source/'builder-checkpoint.c15.json'` hashed against `receipt['checkpoint_sha256']`; `state=self.api.journal.unpack(...)` and `state_hash`/`journal_count`/`journal_hash`/`scope_genesis_hash` cross-checked against receipt + completion (l.354-361, 371-372).
- **Schedule**: `actual_schedule=verified(self.host['schedule'])` must resolve to `schedule/'schedule.json'` and hash to `outer['schedule_file_sha256']`; then `self.schedule=verified_schedule(json.loads(...), expected_digest=outer['schedule_sha256'])` (l.362-366). **This is where `model_context_rows` enters the process.**
- **Scope**: `manifest=verified_json(self.config['source_manifest'])`; `scope=self.api.source_scope(manifest, expected_manifest_hash=manifest['manifest_hash'])` - i.e. `selected_source_scope.source_scope`, the 57027 one-member manifest.
- **Origins**: `self.source_origins={str(source/'source.sqlite'): completion['journal_count']}`, extended by `source_lineage()` (l.391-420) or the single-recovery path (l.381-389).

**The container** is NOT located by `source()` in the base host. Two places:
- `self.host['compact_journal']` = `{path,bytes,sha256}` in the configuration, used by `build_remaining_sunday_prefixes.py:358-364` (compact copier) and by the compact subclass.
- `run_actual_sunday_compact_source.py:56-64`: `witness = self.host['compact_journal']`; `compact_source.CompactSource(witness['path'], expected_sha256=witness['sha256'], expected_bytes=witness.get('bytes'), expected_count=completion['journal_count'], expected_head_hash=completion['journal_hash'])` - **the container is pinned by sha256+bytes AND by the ingestion completion's count+head**. That subclass then answers `source_lineage()` and the `prefix()` anchor read from the container instead of the 11.7 GB raw journal.

**The prefixes**: `self.host['prefixes_directory']` / `prefix-{cycle_index:02d}-witness.json` (l.426) and `self.host['prefix_manifest']` (l.576) for the seeds.

**`_training()` (l.477-518)** - the key line:
```python
self.context,self.decoder,self.optimizer,identity = self.api.native.initialize(
    self.builder, context_rows=self.schedule['model_context_rows'])   # l.481
```
`context_rows` is **the verified schedule's declared `model_context_rows` (4096 here)** - never a code literal. It is guarded by l.480 (`if self.schedule is None: raise ValueError('the verified schedule (model_context_rows) is required before training; verify the sources first')`), so `source()` must have run. `self.builder` is the `OnlinePrefix` installed by `prefix()` (l.471), i.e. training is bound to the cycle's prefix journal. The identities dict (l.483-485) folds in `code_hash=j.evidence_hash(self.code)` - the sha256 of every non-test `.py` under `research/kalshi/frankie_boss` + `research/refrag` - so **any edit anywhere in this map changes the training identity** and invalidates retained preparations.

**`runtime()` (l.770-877)** then: builds `request_id = f"{run_id}-cycle-{index:02d}"`, primes the context cache (`prime_cache`), prepares + admits the critic request, publishes readiness, blocks on the SSM-delivered execution trigger, verifies the service pins, and returns `self.api.driver.SundayRuntime(..., context_encoding=self.host['context_encoding'], context_encoding_options=self.encoding_options(binding))` - where `encoding_options` is the prefix-seed gate (site 5/35).

**Host configuration shape** (the cycle-0 one, retained at `sunday_20260915_package/FB/sunday-launch-20260915/actual-host-final-configuration.json`, schema `FRANKIE_BOSS_ACTUAL_HOST_CONFIGURATION_V1`):
top-level `run_id='frankie-boss-own-source-sunday-20260915'`, `run_directory`, `source_directory`, `schedule_directory`, `source_manifest`, `contract`, `memory`, `mapping`, `retained_witnesses`, `delivery_receipt`, `calculation_result`, `receiver_root`, `receiver_commit`, `model_calls_performed=False`, `training_updates_performed`, **`source_day_required=false`** (declared but read by NO code - grep finds zero readers; inert), and `host_runtime{boss_commit='050c5056...', repository, schedule, schedule_receipt, ingestion_receipt, source_lineage, prefix_manifest (-> full19-prefix-witnesses.json), prefixes_directory, compact_journal (-> journal.compact.sqlite, 569,667,584 B, sha256 19603159...), context_encoding='stacked_v1', service_context=131072, output_budget, transport_protocol='jobs_v1', data_workers=48, tokenizer_directory, expected_tokenizer_sha256, refresh_policy_bands, retained_preparation_recovery, state_defects_and_gaps_reported, development_limitations, completion_workflow_ref}`. All paths are Windows `E:\Codex\Frankie-BOSS-20260915\...`; the live host config is `C:/Codex/Frankie-BOSS-20260919/days/<DAY>/actual-host-configuration.json` (per `day_pipeline.configuration.json` `RunRoot` + `frankie_host_rebuild_prefix_batch.ps1:32`) and is **not in the repo**.

### B4. `frankie_host_rebuild_prefix_batch.yml` - what it re-mints

`/home/user/Markets/.github/workflows/frankie_host_rebuild_prefix_batch.yml` (66 lines, `workflow_dispatch` only, `if: github.repository == 'DavisAI1974/Markets'`, ubuntu-24.04, 150 min). Inputs: `instance='i-0e90ee6110ef609aa'`, `day='20211003'`, `run_root='C:/Codex/Frankie-BOSS-20260919/days'`, `tools_root='C:/tools/Frankie-20260919/Markets'`, `python=.../actual-host-python/Scripts/python.exe`. It only runs `deploy/aws/ssm_run_ps1.py --script deploy/aws/host/frankie_host_rebuild_prefix_batch.ps1 --set Day/RunRoot/ToolsRoot/Python --set CycleLimit=2 --timeout 7200`.

The **.ps1** is where the re-mint happens (`deploy/aws/host/frankie_host_rebuild_prefix_batch.ps1`):
1. **Refuses `CycleLimit != 2`** (l.29) - this precedent re-mints the TWO-cycle batch only (`prefix-batch-02.json`); it cannot produce `full19-prefix-witnesses.json`.
2. Loads `<RunRoot>/<Day>/actual-host-configuration.json`; refuses unless the pinned `prefix_manifest` leaf is `prefix-batch-02.json` and lives in `prefixes_directory`; refuses unless `git -C ToolsRoot rev-parse HEAD == host_runtime.boss_commit` and the tree is clean under `research/kalshi/frankie_boss research/refrag`.
3. **Staleness test**: re-hashes the checkout and compares to the binding's **six code pins** - `script_sha256`->`operations\build_remaining_sunday_prefixes.py`, `copier_sha256`->`journal_prefix_snapshot.py`, `context_selection.runtime_code_sha256`->`sunday_native_runtime.py`, `context_selection.selection_code_sha256`->`context_session.py`, and (when compact) `compact_copier_sha256`->`compact_journal_snapshot.py`, `full_reader_sha256`->`frankie_journal_reader.py`. Nothing stale => nothing moves (re-runnable).
4. **Moves aside (never deletes)** into `<prefixes parent>/superseded/<leaf>-<stampZ>-prefix-batch/`, recording sha256/bytes/mtime read BEFORE the move: `remaining-prefix-binding.json`, `prefix-batch-02.json`, `remaining-prefix-progress.jsonl`, `prefix-01.sqlite`, `prefix-01-receipt.json`, `prefix-01-witness.json`, `prefix-01-packet-seed.json`. **`prefix-00-*` is never a candidate** (explicit `throw` if it ever appears in the list) - cycle 0's retained witness survives untouched.
5. **Re-runs the unchanged builder**: `python operations/build_remaining_sunday_prefixes.py --configuration <cfg> --cycles 2`, exactly as `day_schedule_prefixes.ps1` invokes it, with `PYTHONPATH=ToolsRoot`, logging to `<dayDir>/day-rebuild-prefixes-<stamp>.log`. Verifies `witnesses.Count == prefixes == CycleLimit`.
6. **Rewrites ONLY** `host_runtime.prefix_manifest.sha256` (and `.bytes`) in the day configuration, keeping a dated backup.
7. **Moves `host-identity.c15.json` aside** - the one retained record that pins the configuration.
8. Writes one receipt into the day directory. "Starts, stops and dispatches nothing."

**So what it re-mints**: the batch binding's code sha256 pins, the prefix-01 snapshot/receipt/witness/seed, the batch manifest, and the config's manifest witness. It does **not** touch any data gate - source hashes, the schedule digest, the journal identity, `prefix-00` and the 57027/19 gates all stay enforced. That is exactly the "override the runner problem" precedent in capability-map assumption 1.

---

## C. Sites the capability map MISSED (ordered by consequence)

1. **`FB/operations/build_remaining_sunday_prefixes.py:255` - `cursors[0] != 3261`.** A fourth Sunday literal (the first cutoff cursor) that the map does not name at all. Counted with `57027`/`19`/`20211003`/"full Sunday", this is a 5th value to replace.
2. **`43569`** (the Sunday F_LAST group count) - `run_journal_stack.py:78`, `verify_snapshot.py:225`. A count gate on the emitted conformance, sitting in the same expressions as 57027 but never named.
3. **`member_counts=(57027,)`** - `run_journal_stack.py:77`, `verify_snapshot.py:224`. **A one-element tuple**: the trading day has two members (`(57027, 1975176)`), so this is a *shape* break, not just a value break.
4. **`FB/operations/parallel_source/verify_snapshot.py:26` `EXPECTED`** - the map lists line 26 but not that this one dict is the SINGLE source of all seven Sunday terminal hashes (`sha256`, `state_hash`, `scope_hash`, `journal_hash`, `source_prefix_hash`, `journal_count`, `next_cursor`) and is imported by `run_journal_stack.py:16`. Replacing it is one edit that moves both files.
5. **`FB/operations/run_actual_sunday.py:283` - `for index in range(19)` inside the SSM credential-source validator.** A 19-bound on WHICH request ids may unlock the pod credential. A 20th cycle silently cannot get a key. Not in the map.
6. **`FB/operations/run_actual_sunday.py:122` - `for index in range(19)`** in `await_recorded_principal`, the principal-request uniqueness scan. Not in the map.
7. **`FB/sunday_execution.py:221, 331, 333`** - the map lists only l.208. `0<=index<19` and `run_remaining(cycles=19)` / `1 <= cycles <= 19` are separate gates in the same file.
8. **`FB/sunday_schedule.py:24-25, 75`** - the schedule PRODUCER. The map names `verified_sunday_schedule.py` (the verifier) but not the builder that emits `len==19` and, crucially, `source_dates_required=1` as a **hard-coded literal**. This is where the one-date declaration is minted.
9. **`FB/source_contract_runtime.py:124, 162`** - the map lists only l.21. `source_day':'20211003'` (stamped into the byte-compared `preparation-pins.json`) and `FROZEN_MEMORY_A_20211003.json` (a filename key into the witness roster) are two more day literals.
10. **`FB/frankie_principal_adapter.py:657-660, 773`** - **the day identity in the prompt and in the session-request instruction** ("Sunday 2021-10-03 is the sole source and run day... Its multi-day sequencing is overridden by this current single-day instruction"). The most consequential unlisted site: the model itself is told it is a single Sunday, and the string is part of the hashed durable request. Also `:98, :415-416` (cycle index < 19), `:317, 327, 345, 428` (pre-Sunday Memory A wording).
11. **`FB/raw_mbo_source_manifest.py:14-18` - `EXPECTED_ROSTER`** with the four-date WARMUP/HELD_OUT_BLIND split. The old UTC-day model in data form; its `manifest_hash` is still what hashes both the Sunday manifest and the block manifest.
12. **`FB/operations/day_pipeline.py:74-76, 145-154, 180, 196-209**` - the map lists only l.237. The whole orchestrator is keyed on one `YYYYMMDD`: `runs/<DAY>/`, `BLOCK_{day}_SOURCE_MANIFEST.json`, the upload prefix, the EC2 snapshot label, `minimum_prefixes 19`, and the ingest/stage record reconciliation `'ingest receipt reduced {count} records; {self.day} staged {expected}'`. For a two-partition trading day this refuses by construction unless the day key becomes the trade date and `stage-sources` stages both members.
13. **`FB/operations/day_pipeline.configuration.json`** - `"minimum_prefixes": 19`, `"block": "BLOCK_DAY"`, `"archive": "nymex/ng_mbo_5y_v0/native/2021-10"`. Config-level 19.
14. **`FB/box_standard.py`, `FB/journal_stack_execution.py:64-80, 88-89`, `FB/compact_build_journal.py:64`, `FB/operations/ingest_block_sources.py:162-169`** - the `1189` sites. The map names none of them. Good news: all four DERIVE rows-per-box from the actual count; only the docstrings are Sunday-shaped. The real consequence is stated in `journal_stack_execution.py:77-79` - **a run under this standard does not reproduce the first run's `compact_sha256 19603159...`**, i.e. the trading-day container is a new baseline by design.
15. **`deploy/aws/box/*` - 9 files** with `20211003` as an argparse default, as the S3 key prefix `host-deliveries/20211003/...`, and **inside the box model's prompt text** (`frankie_box_boss_session.py:1184, 1682`; `frankie_box_teach.py:226` - "cycle {cycle} of the 20211003 two-cycle run"). The map names only `frankie_box_bedrock.py`.
16. **`.github/workflows/` - ~15 workflows** with `default: '20211003'`, plus `frankie_boss_source_stage.yml:30-35` hard-coding the single S3 object `glbx-mdp3-20211003.mbo.dbn.zst`, plus `deploy/aws/host/frankie_host_diag.ps1:4` and `deploy/aws/build_readiness_delivery.py:25` with absolute `days/20211003` paths.
17. **`.github/frankie-journal-stack-request.json:4-5` - `"records": 57027, "entries": 114054`.** A committed request file pinning the Sunday counts; the journal job reads it.
18. **`FB/operations/benchmark_native_learner_direct.py:198`** - `if len(steps)!=19: raise ValueError('complete 19-step schedule required')`.
19. **`deploy/aws/host/day_schedule_prefixes.ps1:16`** - `CycleLimit` must be 2 or 19, host-side.
20. **`FB/block_source_scope.py:41`** - `'block manifest members must carry exactly the Sunday member fields, in replay order'`. A gate string, but the module is otherwise already the trading-day-correct binder (validates `member_seams_close_groups`, `halt_boundaries_close_groups`, sums members against `total_mbo_records`).
21. **`FB/operations/ingest_block_sources.py:360-361, 385, 390`** - the `--sunday` CLI branch that routes to `selected_source_scope`. The block branch (`--manifest`+`--sources-dir`, reads `manifest['halt_utc_hour']`, `--session-policy cme_trading_day`) already exists and is the trading-day path.
22. **`FB/operations/restore_sunday_working_tree_identity.py` and `FB/operations/audit_sunday_restoration_manifest.py`** - `FRANKIE_SUNDAY_*` schemas and a hard-coded file roster including `sunday_native_runtime.py`; will refuse after any rename.
23. **Config key `source_day_required: false`** in the cycle-0 host configuration - declared, hashed into `host-identity.c15.json`, and read by **no code**. Worth noting so nobody assumes it is a live switch.

## D. Two structural facts worth flagging before any spec

- **`source_dates_required` is not a gate.** It is in `TOP`, so it is hashed into `schedule_sha256`, but no code compares it. Setting it to 2 changes the digest and nothing else - which means the "one source date" constraint is enforced *only* by `selected_source_scope.source_manifest()` being a one-member frozen dict (site 1). The real one-date gate is the scope, not the schedule field.
- **`model_context_rows` is already clean.** It is a schedule declaration everywhere (`sunday_schedule.py:17-18` refuses a code default; `build_remaining_sunday_prefixes.py:339-340` and `run_actual_sunday.py:480-481` read it from the verified schedule with explicit comments saying "never a literal here"). The capability map's assumption 4 ("the code carries none") is confirmed by measurement: grep finds no `context_rows=` literal on the host path.
