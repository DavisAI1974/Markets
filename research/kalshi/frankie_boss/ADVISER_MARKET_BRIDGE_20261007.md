# Adviser market bridge (remaining_consumers): source report

Role: frankie-remaining-consumers (stages 11, 13 and the Jev sit-in). Owned files:
`deploy/aws/box/frankie_box_adviser_market.py`, `frankie_box_jev_cpu.py`, `frankie_box_experiment_exchange.py`,
`frankie_box_granite_meeting.py`, `research/kalshi/frankie_boss/clm_sidecar/sit_in.py`.

Everything below is SOURCE-BUILT / RUNTIME-UNVERIFIED. Checks: `ast.parse` without project imports on the five
files; `git diff --check` on them. No tests, runs, installs, dispatch, model or data calls. One read-only account
call (EC2 DescribeInstances, us-east-1). A fresh independent review is required before integration.

## 2026-10-07 evening (Greg's resumption; the redirects: all-99 first, day-quantity agnostic, Jev = Granite runtime)

### Built

**frankie_box_adviser_market.py** (303 -> 1087 lines)
- Token stacks on the picture text (`render_stacks`, `_Stacker`, `_unstack`, `_dedup`, `_resolve`, `unstack_text`,
  `verify_render`, `render_summary`): the exact typed picture tree (`_exact_market_text`: `mapping`/`list`/`tuple`
  with c15 `pack` scalar tags) is spelled in `frankie_box_stacked_text` STACKED_TEXT_V1. Layers, each kept only
  when it shortens, each proven by parse-back: L1 tag-to-atom (`V`/`H`/`X`), column tables `C` for same-keyed
  mapping lists, `S` repeats, `Q` dictionaries, `N` integer sequences with the codec's own `I`/`D`/`R`/`E` recipes
  (`granite_context_stacked._integers`, called, not copied), L3 content-addressed dedup of repeated subtrees
  (`$dictionary`/`$ref`, applied only when the character arithmetic saves), and a DIGEST_V9 table candidate for
  flat tables (`frankie_box_digest_render.render_table`/`parse_table`, accepted only when it parses back to the
  same rows with identical float bits). Non-string map keys travel as `$keyed`; keys starting with `$` are escaped
  `$$`. Proof chain before any use: `parse(spell) == tree` and `unstack_text(text) == picture_text` byte for byte;
  `text()` re-proves on every read; `check()` pins the render's sha256 to the exact picture. Character counts are
  recorded per layer; tokens are NOT guessed: the consuming pieces count the stacked text with the server tokenizer
  (Jev: `state['picture_tokens']`; meeting: `system_prompt_tokens`) and that count against `source_chars` is the
  canary at the one-day run. Nothing dropped, rounded or summarized; the legend is emitted once per prompt.
- All-99 coverage (`registry_layers`, `ROUTES`, `ROLES`, `all_99_coverage`, `all_99_with_consumer`,
  `all_99_summary`): every layer_id of the pinned 99-layer registry (from the committed crosswalk
  `research/kalshi/frankie_boss/audits/CROSSWALK_SUNDAY_CYCLE0_FEED_33746436209_20260916.json`, pinned by
  `knowledge/CYCLE_CALCULATION_PINS.json`, registry sha 239a1480; fallback to the committed code lists with the
  unnamed groups said so) gets one row per day-instant: entry, group, role (raw / calculation / clock / control /
  knowledge / arm / sealed_answer / shadow / output), the route into the picture and the disposition
  (arrived / arrived_partial / thin / absent / completed_only / teacher_seat / arrived_at_consumer /
  not_loaded_by_this_piece / enforced_by_rule / historical_not_bound / not_applicable / withheld_by_rule /
  disabled / append_only_output / not_on_experiment_path) with its reason. Picture routes test the actual row keys
  observed at or before the instant (frames `book`/`activity`/`integrity`/`observation`/`input_records`, prices,
  structures, native member, the raw record's SDK fields, `picture.at` clocks, update `known_at_ns`); roles are
  never collapsed into numeric columns. The list is on every piece's `workflow_report.use.all_99_coverage`
  (projected whole by the existing reporter's `workflow_report_block`) and its counts are one line of the prompt.
- `workflow_report(..., consumer=...)` carries the piece's own consumer rows, `shared_market_render` and the
  all-99 list; `reference()` carries the render and all-99 summaries.
- Missing-coverage rule unchanged from the earlier rewrite: the cutoff instant is never rejected for a failed,
  unpaired or unknown outcome or an absent layer; integrity contradictions still raise.

**frankie_box_granite_meeting.py** (1406 -> 1622 lines)
- `meeting_input`: the WHOLE shared market picture (`AM.text`, the proven stacked spelling) in
  `given['shared_market_picture']` beside the exact reference. `_meeting`: the picture is a section of the system
  prompt; the system prompt is counted ONCE with the server tokenizer before any call (`system_prompt_tokens`);
  over `input_token_cap_per_call` every item is left open by code with kind `input_cap_system_prompt` and the
  count, no call, nothing trimmed (the only accepted reason Granite does not see the whole picture, visible on
  the receipt and the inspection markdown). The number rule (`validate_action`) is unchanged.
- `local_runtime`: THE shared runtime definition (pins from GRANITE_MEETING_RUNTIME_V1.json, the setup script's
  `provenance.json` naming the extracted llama-server, the model path under /opt/frankie-box/granite, the thread
  rule, the exact install requirements and the gate reasons). `--route local` is the default; absent
  `--binary/--model` resolve to the canonical paths and the gate refuses by name; inputs-only receipts also list
  what the box still needs. `--local-runtime` prints the definition. The GitHub route stays listed, inputs-only
  from here (the Run dispatches it).
- `LlamaServer._post`: per-call ceiling from `params['call_ceiling_seconds']` (default 600). `host_cpu()`
  (model name, avx512/amx flags) recorded in `runtime.effective`; phase `timings` on the record;
  `meeting_workflow_report(..., context=, route=)` carries the picture delivery, the counted tokens against the
  cap, the local route, host CPU, timings and the all-99 consumer rows.

**frankie_box_jev_cpu.py** (493 -> 654 lines)
- Greg's decision applied: Jev binds to `frankie_box_granite_meeting.local_runtime` (symbol `SHARED_RUNTIME`);
  `runtime_check` refuses a runtime file naming another binary/model, carries the shared gate reasons, resolves
  `cpus={kind: lane_workers, count: n}` from the held lane's workers (coordinator excluded), binds Greg's approval
  (`approved={by, at, approval_sha256}` over the decided rows and every proposed field; any change re-requires
  approval) and refuses visibly otherwise (status.json through main). `PROPOSED_JEV_CPU_RUNTIME_V1` with one-line
  reasons; `--propose` prints it with the `approval_sha256` to sign. Same `LlamaServer` transport, approved
  threads and per-call ceiling. Reuse of the exchange's retained read of the same source and cutoff before a
  fresh walk (one full ordered read of the day saved per Jev turn when scopes match; recorded, never assumed).
  Phase timings, host CPU and the all-99 consumer rows on the receipt.

**sit_in.py** (758 -> 796): `picture_tokens` (the stacked picture section counted once by the server tokenizer,
retained in the durable state), `material_use` render/all-99 counts, `all_99_for_jev`. **experiment_exchange.py**
(+13): the exchange's consumer rows (lessons, accumulated knowledge, brain, late knowledge, rules, walls, outputs).

### Day-quantity sweep
No literal or branch in the five owned files keys on a run holding one, three or N days (the only `16` is the
lane rule; "ONE classroom-arm day" in the exchange docstring is per-day semantics). Nothing removed; stated in
the module docstrings.

### JEV_CPU_RUNTIME_V1 (decided rows from the shared runtime; proposed rows for Greg)
| row | value | status |
|---|---|---|
| weights | IBM Granite 4.2 3B Q4_K_M (pins.model_sha256) | DECIDED (Greg) |
| build | llama.cpp b11440 llama-server (pins) | DECIDED |
| runtime path | `local_runtime` + `LlamaServer`, local child on the owning box, CPU only | DECIDED |
| cpus | lane_workers, count 15 (coordinator excluded) | PROPOSED |
| threads | 8 (the lane is 8 physical cores x 2 threads; r7i) | PROPOSED |
| context_size | 32768 | PROPOSED |
| max_output_tokens / min_output_tokens / token_margin | 4096 / 1024 / 512 | PROPOSED |
| piece_chars | 54000 | PROPOSED |
| call_seconds / process_seconds | 1800 / 14400 (unmeasured) | PROPOSED |
| completion | comparison required; unparsed listed | PROPOSED |

### AWS and skills
Skills: api-and-interface-design, performance-optimization, observability-and-instrumentation,
experiment-orchestrator (Skill tool); aws-compute, aws-storage, querying-aws-s3, aws-billing-and-cost-management
(`retrieve_skill`), registry search (`search_documentation`, agent_skills). Account call: EC2 DescribeInstances
(us-east-1, read-only): i-035994afa8bdf66a5 r7i.8xlarge 16c/32t stopped; i-0d17573dbce871520 r7i.4xlarge 8c/16t
stopped. Applied: instance facts to the thread proposal and the CPU-backend record; the exchange-context reuse;
tokenizer-counted canaries. Rejected for these pieces: S3 byte-range/conditional reads, S3 Select/Athena, S3
Metadata/Storage Lens, parallel transfer (every input of the meeting, exchange, Jev and adviser is owner-local on
the box's disk; the local route moves no object; the GitHub route's archive transport is the unused fallback).
Cost: the local route runs inside the already-held lane; no extra instance or runner minutes.

### Open
Runtime-unverified throughout. Token effect unmeasured until the one-day canary. Greg's approval of the proposed
Jev rows. Box install of the pinned runtime (next session, Greg's go). The full time-addressable model
query/history protocol remains an explicit gap. Cross-owner requests: `frankie_box_granite_meeting.sh` (pass
`--route local` instead of `--inputs-only` when LLAMA_SERVER/GGUF_MODEL are unset); Run.jev (ccode_step8): the
runtime file is still the plan's `jev_runtime`; no new argument is needed since Jev imports the shared definition,
but the request may carry `shared_market_context` (the exchange's retained read) to skip the walk explicitly;
`frankie_box_experiment_teacher` (workflow-reports): retain the teacher's own read of its cutoff as
`shared-market-context.json` so the exchange's walk is saved too; `knowledge/GRANITE_MEETING_RUNTIME_V1.json`
`settled.hosts_in_order`: the local child on the owning box first (documentation of Greg's decision).
