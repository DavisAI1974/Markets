# Step 6 module/API and AWS compute review — 2026-10-07

SOURCE-BUILT / RUNTIME-UNVERIFIED. Reviewed current integration source at
`439cb0bf71968f30f94b696b85acfaa00dccc3c1` on `ccr-5fce7de3-xa4hfg`, including the
direct Codex corrections after CCode's sixth return. The older transport/spawn findings
are addressed in this source; they are not new assignments. CCode currently owns Step 8A.

Applied using-agent-skills, context-engineering, API and Interface Design, git workflow
and code-review skills. Retrieved AWS `aws-compute` through AWS documentation search,
then its `references/systems-manager.md`. AWS calls retrieved documentation only.
The user-authorized review uses source/diff and AST parsing without project imports;
no tests, synthetic exercise, validator framework, installs, model/data/reproduction
calls, account inspection, compute action, dispatch or E2E. No commit or push here.

## Contract and ownership map

| Boundary | Contract and owner | Current disposition |
|---|---|---|
| `Run.voice` → meeting launcher | Original completed exchange's Frankie view, stable `<run>/meeting/<day>` output, plan brain; staged code identity | Stable output is reused; completed model work is not rerun locally. Absent runtime environment means inputs-only. |
| `Run.child` → CPU ledger | `voice` belongs to `DAY_RUN_STAGES`; inherited day booking or existing exact 16-CPU booking; taskset confines the child | No new host/lane. Giant evidence remains on its owner. |
| `_meeting` → `LlamaServer` | Pinned 3B Q4_K_M, pinned llama.cpp, 16,384 context, 8,192 input cap, 400 output, six turns, 3,000 seconds; `threads: null` | No pin/parameter or training change. Ephemeral local process, loopback transport, coordinator only. |
| Model reply → `validate_action` | Exact top-level action keys, known action/seat, text, attributable cites, existing request binding | Model replies are untrusted; rejected turns stay in retained evidence. Narrow boundary fixes below. |
| Item → progress | `FRANKIE_GRANITE_MEETING_ITEM_PROGRESS_V1`, item and complete binding hash | Pending chat intent is durable before possible send. Terminal round and result are one durable write. |
| Meeting → brain | `FRANKIE_GRANITE_MEETING_V1`, same run/day/exchange bytes/hash, all items discussed or explicitly unreached; four categories; zero coordinator evidence weight | Complete record publishes through `publish_meeting_record` / `write_meeting_entry`. Requested tests remain `requested_not_run`. |
| Startup failure → day runner | Bound `runtime_failed` receipt with original input and binding witnesses | Current runner, brain reader and queue already accept the recorded non-blocking refusal. Other child failures remain failures. |
| GitHub runner → owning lane | Artifact with record/progress/evidence and return witness; optional PUT sends record bytes | Explicit `import_meeting_record` rechecks owner plan, completed ROOT and exchange receipts before publication. Download/import orchestration is still absent. |

`inputs_only`, `refused` and `runtime_failed` are operational dispositions, never proof
that a facilitator ran. A complete meeting may legitimately retain unresolved calls,
open items and unreached items; it is a completed record, not scientific resolution.

## Replay and unknown outcomes

- Local `meeting()` holds one output-directory flock. Binding pins exchange, meeting
  input, charter, rules, config, parameters, binary and model. A changed binding refuses
  reuse. Existing complete `meeting.json` repairs publication without new model calls.
- Every chat gets a durable pre-send intent; request transport marks possible send
  before transmission. A definite never-sent error clears pending state. A possible
  send without a recorded reply stays unknown, preserving completed rounds and whole
  error/reply evidence. Local restart closes that item open rather than repeating it.
- Per-attempt start records precede process spawn; terminal ownership is now `_meeting`.
  Unique attempt evidence and stderr, unfinished attempt discovery, and separate completed
  call versus unknown-intent counts are present. Absolute request deadlines include
  status/header/body/chunk parsing; partial wire/body evidence is retained.
- The configured 3,000-second clock is recreated for each local attempt. The current
  code bounds each attempt, not cumulative lifetime across repeated process crashes.
  Do not claim a total-across-restarts duration guarantee.

## Source defects corrected in this review

Ownership for these surgical edits was requested from and granted by the coordinating
agent. Only `deploy/aws/box/frankie_box_granite_meeting.py` source was changed.

1. **A null request binding could be admitted.** `validate_action` unconditionally
   inserted an absent `claim_id` as `None` into `allowed`, permitting `binds_to: null`
   on a claimless item. It now adds only a present claim ID and refuses empty bindings.
   Existing nonempty proposal/claim/open-item identifiers retain their behavior.
2. **Malformed model fields could escape the refusal path.** `cites` was iterated
   without checking list shape; `source_sha256` and `binds_to` could be unhashable
   containers when tested against sets. The existing boundary now checks the declared
   list/string/null shapes and known seats before use, returning the existing refusal
   tuple. No separate validation framework or extra internal validation was added.
3. **`RESOLVED` could coexist with code-seeded open items.** Frankie `RESOLVED_*` and
   no Frankie disagreements were the only checks, while BOSS/science proposals or
   missing evidence could remain. The action now refuses while `item.open_items`
   is nonempty. Granite cannot close those code-owned items; `LEAVE_OPEN` remains valid.
4. **Whole model hashes allocated model-sized Python bytes.** `witness_file` used
   `Path.read_bytes()` for the configured 2,244,011,552-byte GGUF at the gate, binding
   and final record. It now hashes the entire file sequentially in 1 MiB chunks,
   counting bytes actually read. `runtime_provenance` uses the same helper for the
   binary and every manifest file. Path/bytes/SHA-256 witness shape and full-file
   verification frequency are unchanged; no cache or evidence omission was introduced.
   All callers consume only that witness shape, never the old temporary file bytes.
5. **Voiced numbers did not require citations.** The boundary checked supplied cites
   but admitted existing seat numbers with `cites: []`. It now requires each voiced
   numeric token to appear among the citations already checked against seat sources.
6. **Retained knowledge index/findings were absent from the prompt.** The existing
   `meeting_input.knowledge_index` and `teachers_findings` summaries now appear as an
   explicit retained-context section in the system message. They add no new private
   material or empirical claims; the full resulting transcript still passes the
   existing exact token counter/cap, with no truncation. In-progress retained transcripts
   with a different original prompt/input refuse a new call; complete or unknown-call
   dispositions are still consumed without a call. Prior evidence is never rewritten
   to look as if it had received this context.

## Remaining concrete gaps, outside these edits

1. **Runner replay lacks retained-state intake.** The standalone GitHub workflow
   accepts an exchange URL, output URL and inputs-only flag, but no prior attempt
   artifact/restore contract. Each fresh job starts a new `work/meeting/out`. Re-running
   a failed job can repeat model work whose prior result is unknown even though local
   restart is conservative. The smallest next slice is owner-bound retained-artifact
   intake (binding/progress/evidence included) before any second dispatch, with a
   refusal if prior completion cannot be established. This needs the dispatch/transport
   owner; an uploaded artifact alone is not a restore mechanism.
2. **Actual accumulated-knowledge content scope remains open.** The local route's
   already-retained label/hash index and findings summary now reach the prompt, as
   corrected above. This does not deliver the contents of the indexed knowledge.
   The GitHub route also supplies no brain, so it cannot independently acquire that
   owner-local index. A governed owner input/return envelope is still needed there.
3. **Requested test completion is not a Step 6 capability.** Meetings and reports
   retain `requested_not_run`; this review found no consumer translating those meeting
   requests into checked scientific execution/publication. Preserve this state until
   the existing scientific owner explicitly binds an authorized operation; do not
   promote a request or a coordinator agreement into evidence.
4. **Host CPU count can exceed the held affinity.** `resolve_threads` follows the
   pinned `threads: null` rule using `os.cpu_count()`. `Run.child` confines AWS work
   to its held 16 CPUs, but on a larger host the server may create more threads than
   available affinity CPUs. No allocation or runtime choice was changed. An approved
   effective-affinity interpretation would address oversubscription without another
   lane; it must keep the runtime contract and recorded host/effective counts explicit.
5. **Activation/return remains incomplete.** `Run.voice` does not supply runtime
   paths itself, and no automatic GitHub download/import owner exists. Runtime staging,
   chosen first E2E host and explicit execution authorization remain prerequisites.
   The complete local publication and `runtime_failed` reader hooks already exist;
   do not ask CCode to rebuild them.

## AWS tools and performance applicability

| Option examined | Application to Step 6 | Decision under this source-only scope |
|---|---|---|
| Sequential EBS I/O and throughput limits | Model hashing and model loading are large sequential reads; volume and instance throughput both matter | Implemented bounded-memory sequential hashing above. No EBS type, size, IOPS, throughput or read-ahead change. |
| Existing process CPU affinity | Avoid creating host-count threads inside a smaller booked CPU set | Concrete issue recorded above; no change to pinned `threads: null` or lane counts. |
| NUMA placement tools | Potentially relevant only if the actual held host spans NUMA nodes | No topology is established here. No `numactl` install, policy guess or process repinning. |
| Systems Manager existing host control | Existing managed-node/credential/network path can carry future owner launch/status operations | Documentation does not establish these host prerequisites. Reuse existing staged owner flow; no new agent/service/account call. |
| Instance-family/CPU-option changes | Could change compute/memory behavior | Outside existing held-lane and pinned-runtime contract; no replacement host, SMT change, GPU or paid service. |

AWS documentation retrieved on 2026-10-07:

- [EBS I/O characteristics and monitoring](https://docs.aws.amazon.com/ebs/latest/userguide/ebs-io-characteristics.html):
  I/O size, sequential merging and volume/instance throughput limits. The Python memory
  improvement is an inference from our source, not a measured AWS speedup.
- [AWS NUMA review guidance](https://repost.aws/knowledge-center/ec2-review-numa-statistics):
  topology must be established before choosing placement; commands/install not run.
- AWS `aws-compute` skill and `references/systems-manager.md`: instance storage durability,
  existing managed-node/credential prerequisites and command delivery ownership. No
  account state was queried or changed.

Verification: inspected the complete changed functions, their callers and the complete
diff; AST parsing without imports and `git diff --check` only. No throughput, latency,
CPU use, model quality or E2E result is claimed. Step 6 remains globally incomplete.
