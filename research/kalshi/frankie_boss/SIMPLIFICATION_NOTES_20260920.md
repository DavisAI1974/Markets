# Simplification notes: the 2026-09-20 identity/supersede family (notes only, nothing edited)

Produced by the code-reviewer persona with the code-simplification skill loaded, at Greg's request, for the
architect (companion to `NOTES_FOR_CLAUDE_CHAT_20260920.md`). Scope: `feedback_cycle.py`,
`sunday_execution.py`, `sunday_native_runtime.py`, `operations/{declare_identity_supersede.py,
run_actual_sunday.py, day_pipeline.py}`, the five `deploy/aws/host/frankie_host_*.ps1` written today,
`deploy/aws/ssm_run_ps1.py`, the tests and the three CI workflows. Behaviour preserved exactly in every
proposal; every content-hash check stays; nothing here is for the run in flight.

Verdict on the day's code: it is correct and every override is receipted. The complexity is accidental and
comes from one thing built four times under pressure: "read the operator declaration, mask the provenance
keys, compare content, record acceptance". Below is where it lives and the smallest safe form.

## 1. Duplication and accidental complexity

### 1a. The declaration file is read in two coordinator methods and written by a third program

- `feedback_cycle.py` `_binding_supersede` and `_export_pin_supersede`: identical
  `Path(str(self.path)+SUFFIX)` / `exists` / `json.loads` / `except ValueError` /
  `entries if type(entries) is list else []` blocks.
- The acceptance-file append (read, dedupe, `json.dumps(sort_keys=True, indent=1)`) appears in both
  `_binding_supersede` and `_record_pin_supersede`.
- `operations/declare_identity_supersede.py` reads/writes the same file a third time with the suffix
  spelled as a second literal (`DECLARATION_SUFFIX` vs `IDENTITY_SUPERSEDE_SUFFIX`), and the embedded
  Python of `frankie_host_binding_diff.ps1` reads it a fourth time.

Simplest safe form (one place, imported by all three):

```python
DECLARATION_SUFFIX = '.identity-supersede.json'
ACCEPTED_SUFFIX = '.identity-supersede-accepted.json'

def declarations_for(cycles_path, request_id):
    """Operator declaration entries naming this request; [] when absent or unparseable."""
    path = Path(str(cycles_path) + DECLARATION_SUFFIX)
    if not path.exists(): return []
    try: entries = json.loads(path.read_bytes())
    except ValueError: return []
    return [e for e in (entries if type(entries) is list else []) if type(e) is dict and e.get('request_id') == request_id]

def append_accepted(cycles_path, records):
    path = Path(str(cycles_path) + ACCEPTED_SUFFIX)
    existing = json.loads(path.read_bytes()) if path.exists() else []
    added = [r for r in records if r not in existing]
    if added: path.write_bytes(json.dumps(existing + added, sort_keys=True, indent=1).encode())
```

### 1b. The retained-stage reader exists three times

`CycleCoordinator._load` (read + digest check), `declare_identity_supersede.saved_stage` (same SQL, same
digest check, read-only URI, `SystemExit` instead of `ValueError`), and the probe's embedded Python (same
SQL, no digest check). Form: a module-level `load_stage(connection, request_id, stage)` in
`feedback_cycle.py`; `_load` delegates to it; the helper opens its `?mode=ro` connection and calls it; the
probe's Python moves to a checked-in `operations/binding_diff.py` and calls it too.

### 1c. The code-identity map is computed in two files, on two different roots

`run_actual_sunday.py` (`self.code`, rooted at `host_runtime.repository`, `host_script = sha(__file__)`) and
`declare_identity_supersede.code_identity` (same comprehension, rooted at `--tools-root`,
`host_script = sha(repo/'.../run_actual_sunday.py')`). The file-sha helper is written three times. The two
roots are the same checkout only by configuration; if they ever differ the helper's `new_code_hash` is not
the hash the coordinator sees and the supersede refuses. One function removes the drift:

```python
# research/kalshi/frankie_boss/code_identity.py   (stdlib only)
CODE_ROOTS = ('research/kalshi/frankie_boss', 'research/refrag')
HOST_SCRIPT = 'research/kalshi/frankie_boss/operations/run_actual_sunday.py'

def sha_file(path): ...                      # the one 4 MiB block loop

def code_identity(repo):
    repo = Path(repo)
    code = {str(p.relative_to(repo)): sha_file(p) for root in CODE_ROOTS
            for p in sorted((repo/root).rglob('*.py')) if 'tests' not in p.parts}
    code['host_script'] = sha_file(repo/HOST_SCRIPT)
    return code
```

Behaviour note: today `host_script` hashes `__file__`; after the change it hashes `repo/HOST_SCRIPT`. Same
bytes whenever the runner is invoked from `host_runtime.repository`, which `__init__` already requires via
`git rev-parse HEAD == boss_commit`; prove equality in a test before switching. This is also where
`science_hash`/`tooling_hash` will live once Greg declares the list.

### 1d. Provenance pins and content pins share one loop and one compare

`_export_verified` applies the `superseded` map to all five pins although only `boss_commit`/`agent_commit`
can ever be in it; the binding is built with `training_identities=checkpoint.identities` whole, so
`code_hash` sits inside a content record and `_binding_supersede` reconstructs the masked view by hand
twice. Form, no behaviour change:

```python
CONTENT_PINS = ('request_id', 'controller_checkpoint', 'native_checkpoint')   # never superseded
EXPORT_PINS  = ('boss_commit', 'agent_commit')                                # operator-declarable
```

plus a single `_masked(saved, replace)` applying a `{('training_identities','code_hash'): new_hash,
('controller','arm_hash'): new_arm}` map, so "what counts as provenance" is one table read by both the
compare and the acceptance record. After the identity split that table is where `science_hash` stays out
and `tooling_hash` goes in.

### 1e. `_binding_supersede` is one 58-line function with nine `return False`s

Split into a pure `_declared_binding_supersede(request_id, saved, binding) -> entry | None` (shape checks,
masked compare, declaration match; no writes) and `_apply_binding_supersede(...)` (archive, update, acceptance
record). The `arm_change` flag travels in `entry`; the test can assert the pure half without a database write.

### 1f. `run_cycle`'s two plan branches repeat each other and hand-list the plan keys

`learning_config(...)` is built in both branches; the retained branch rebuilds `bridge` by hand while the
new-plan branch gets it from `assemble_request`; eleven plan fields are written and seven compared by a
hand-written `or` chain with nothing tying "what is written" to "what is checked". Form: hoist `config`,
construct `bridge` once after the branch, and a `RUNTIME_PLAN_FIELDS` table used by both writer and comparer.
Plan bytes and `learning_config_hash` unchanged. Science-adjacent record: goes last.

Trap to record, not fix: `_plain` exists twice with the same name and DIFFERENT semantics
(`feedback_cycle._plain` turns lists into tuples; `sunday_execution._plain` preserves lists). The binding-diff
probe imports `feedback_cycle._plain` to rebuild a plan written with `sunday_execution._plain`. It reported
the right two diffs today because the divergent path carried no lists; the two must not be merged, and the
probe should import the one the plan was written with.

### 1g. `day_pipeline.py` writes the same receipt five ways and the dedication gate twice

CPU-dedication formula and message in `gate_of` and `record_external`; receipt envelopes hand-built five
times; `host_stop` and the ingest branch of `stop_compute` are one shape. Form: `_dedication(value)`,
`_record(stage, **fields)`, `_stop(instance, region, file)`. `_ssm` is already the single `--set` sender.

### 1h. The five host scripts copy one preamble and one epilogue

Sent verbatim by design, so each carries its own copy of: the required-variables loop; CycleIndex default +
regex; `$dayDirectory`/`$cfgPath`/`Test-Path`/`ConvertFrom-Json`; the tools-HEAD refusal; a SHA256 helper;
`$stamp` + receipt into the day directory + `RECEIPT` last line; the live-runner refusal. The copying produced
inconsistencies: `binding_diff` skips the CycleIndex regex; `advance` does not `Test-Path` the configuration;
only `declare` refuses a live runner (the supersede, which MOVES the run's state, does not; a behaviour
question for Greg, not a simplification).

Form that keeps "sent verbatim, no dot-sourcing on the host": `ssm_run_ps1.py` already prepends text. Add one
checked-in `deploy/aws/host/_frankie_host_prelude.ps1` defining `Require-Variables`,
`Read-DayConfiguration`, `Assert-ToolsHead`, `Assert-NoRunner`, `Get-Sha256`, `Write-Receipt`, and send
`preamble + prelude + script`. Each script becomes its own logic only. The text tests then read the RENDERED
command, exactly what the host runs.

### 1i. The `--set` lists and the input validation live in every workflow

Each workflow restates the `--set "Name=$ENV"` list; the value rules (40-hex sha, no apostrophe) are enforced
only on the host side or by the sender's refusal, which cost run 35533704067 a round trip. Form:
`--set-file vars.json` on `ssm_run_ps1.py` (same refusal rules per value) and `pattern:` on inputs with a
fixed shape.

### 1j. The pipeline's test family is a hand-written list, and two CI workflows exist because of it

`frankie_journal_stack.yml` names twelve globs by hand; `frankie_cycle_identity_ci.yml` exists because that
list missed two files; `frankie_host_scripts_ci.yml` lists four test files and repeats its `paths:` block
twice. See section 4.

## 2. Proposed layout after simplification

```
research/kalshi/frankie_boss/
  code_identity.py            NEW, stdlib: sha_file, CODE_ROOTS, HOST_SCRIPT, code_identity(repo)
                              later: SCIENCE_MODULES (Greg's list), science_hash, tooling_hash
  feedback_cycle.py           keeps CycleCoordinator; gains module-level load_stage(),
                              declarations_for(), append_accepted(), CONTENT_PINS/EXPORT_PINS,
                              _masked(); _binding_supersede split pure/apply
  sunday_execution.py         RUNTIME_PLAN_FIELDS table; one bridge/config construction
  operations/
    run_actual_sunday.py      imports code_identity (one call)
    declare_identity_supersede.py
                              imports code_identity, load_stage, DECLARATION_SUFFIX; ~40 lines
    binding_diff.py           NEW: the Python now embedded in frankie_host_binding_diff.ps1,
                              importing load_stage and the SAME _plain the plan was written with
  tests/
    host_script_contract.py   NEW shared checks (see 4)
    family.py                 NEW: the test family derived from the tree (see 4)
deploy/aws/
  ssm_run_ps1.py              --set unchanged; sends preamble + prelude + script; --set-file
  host/_frankie_host_prelude.ps1   NEW
  host/frankie_host_*.ps1     bodies only
```

| today | after |
|---|---|
| `_binding_supersede` (58 lines, I/O + logic) | pure `_declared_binding_supersede` + `_apply_binding_supersede`; reads via `declarations_for`, writes via `append_accepted`, masks via `_masked` |
| `_export_pin_supersede` + `_record_pin_supersede` | 6 lines each over the shared helpers; `EXPORT_PINS` shared with `_export_verified` |
| `operations/declare_identity_supersede.py` | thin: `code_identity()`, `load_stage()`, one entry, one receipt |
| `frankie_host_declare_identity_supersede.ps1` | prelude + 6 lines (the helper call) |
| `frankie_host_binding_diff.ps1` | prelude + one `& $Python operations/binding_diff.py ...` |
| `frankie_host_supersede_code_bound_state.ps1` | prelude + the candidate list, the scan and the move loop; identity reading via a checked-in `operations/read_identity_records.py` |
| `frankie_host_advance.ps1` | prelude + git steps + the one textual rewrite; the single advance operation |

## 3. After the `science_hash` / `tooling_hash` split: what retires, what stays

Assumption: only `science_hash` enters `training_identities`, the checkpoint digest, `arm_hash`, the
coordinator binding and the export manifest; `tooling_hash` and `boss_commit` are recorded as labels.

RETIRED (their only reason was a tooling advance re-minting a science pin): `_binding_supersede`,
`_export_pin_supersede`, `_record_pin_supersede`, the two suffix constants and the `superseded=` parameter of
`_export_verified` (`boss_commit` becomes a recorded label; `request_id` and both checkpoints stay hard);
`operations/declare_identity_supersede.py` with its host script, workflow and tests;
`frankie_cycle_identity_ci.yml` (retired by the tree-derived family); `frankie_host_supersede_code_bound_state`
as a routine operation (kept in git history as the rare receipted override for a genuine science change
mid-run, if Greg wants that door at all). The re-prepare branch in `runtime()` (842ec2ee) is NOT retired: it is
a correct resume rule regardless of why the record is absent; it just stops being exercised by advances.

STAYS: `frankie_host_advance` as the one advance operation (gaining "refuse if `science_hash` changed",
dropping the one-day request-id grep); the binding-diff as a read-only diagnostic (`operations/binding_diff.py`);
`frankie_host_restore_mapping_index` (the seed of the preflight stage); `code_identity.py` holding both hashes
and Greg's declared list; every content check in `_export_verified`, `_save`, `sunday_execution._save`,
`current_training_identity`.

## 4. Tests

Duplicated: the "required variables" check is written five times; "no path literal / no credential" five
times with THREE different definitions of a path literal (pick the strictest, in one place); "workflow passes
every variable by `--set`" four times; the `ssm_run_ps1.preamble` contract twice byte for byte. Form:
`tests/host_script_contract.py` with `check_required_variables`, `check_no_path_literal_or_credential`,
`check_workflow_sets`, `check_receipt_last`, driven by one `SCRIPTS` table; each `test_host_*.py` keeps only
what is specific to that script.

Missing:
1. The round trip the two halves were never tested together on: run `declare.main()` against a store with a
   stale binding + export stage, then `CycleCoordinator.run()` on that store with the new identities, and
   assert the acceptance records equal the declaration's old values. A rename on either side passes both
   suites today and refuses on the host.
2. `code_identity(root)` equals `ActualHost.code` on the same tree (`evidence_hash` equality).
3. The re-prepare branch of `runtime()` (842ec2ee): ran live four times today, zero automated coverage (the
   only test touching `prime_cache` stubs it).
4. `_export_verified` through `run()` with a moved pin on a real manifest (the fixture stubs it; the "records
   nothing when the manifest lacks the pin" behaviour of 696f2275 is pinned by nothing).
5. A check that no test file is silently outside the family.

Deriving the family from the tree (`tests/family.py`): `family()` = every `test_*.py` minus an explicit
`EXCLUDED` map with reasons (empty today), `NEEDS_TORCH_FREE` for the `--noconftest` set, and one test asserting
`set(family()) | set(EXCLUDED) == {every test_*.py}`. The checks job becomes one `pytest research/kalshi/frankie_boss/tests`
plus one `--noconftest` run of the torch-free set; the two extra CI workflows and their `paths:` lists collapse
into it; the family also runs on push to any branch touching `research/kalshi/frankie_boss/**`.

## 5. Order, with risk

1. `declarations_for` / `append_accepted` / `load_stage` / `CONTENT_PINS`-`EXPORT_PINS` in `feedback_cycle.py`
   (1a, 1b, 1d). Pure refactor; existing tests cover every branch; no hash, record format or file name changes.
   Risk low. Precondition: not while a run is open (any `.py` edit re-mints `code_hash` today).
2. One `code_identity()` for both callers (1c), with the equality test first. Risk low-medium: the hash must
   be byte-identical. Same precondition.
3. Shared test contract + one path-literal regex + tree-derived family (4). No production risk; the strictest
   regex may fail on an existing script, which is a finding. The workflow edit waits for the launch rule to lift.
4. Host prelude via `ssm_run_ps1.py` (1h). Risk medium: changes every command sent to the host. Mitigation:
   text tests on the rendered command; dispatch the read-only cycle-status script first. Non-run day.
5. `day_pipeline.py` receipt/dedication/stop helpers (1g). Risk low; receipt bytes unchanged under `sort_keys`.
6. `run_cycle` plan table and single bridge/config construction (1f). Risk medium: the plan is a retained
   record hashed into `learning_config_hash`; land last with a fixture asserting the plan bytes are unchanged.
7. `--set-file` and input patterns (1i). Risk low; additive.

The identity split itself is not on this list: it is Greg's design call and a behaviour change; items 1-3
make it a small diff when it happens.
