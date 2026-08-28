# Spec: Frankie lossless raw-MBO two-day blind stream benchmark

Date: 2026-08-28

Branch: `chatgpt/frankie-raw-mbo-benchmark-20260828`

Governing process: `addyosmani/agent-skills` release `0.6.7`.

## Objective

Upgrade only the market-evidence seam of the proven October 4-5 two-Frankie Work-mode program from the prior reduced/non-full-MBO seconds surface to the canonical native Databento MBO stream.

The raw-MBO benchmark must preserve the existing scientific roles, authority, blind wall, output preservation, and RT-first freeze semantics while ensuring every native MBO action is available to each Frankie in causal receive order without seconds collapse, MBP substitution, event sampling, or Step-1-derived input.

No Frankie/model launch is authorized by this spec alone.

## Brownfield authority retained

Retain and adapt around, rather than broadly rewrite:

- `research/kalshi/ng_exhaustion_two_frankies_workmode_packet_2day_20260825.py`
- `research/kalshi/ng_exhaustion_two_frankies_workmode_coordinate_2day_20260825.py`
- existing Real-Time Frankie then Forecaster Frankie role order;
- existing first-lock owner and one-way RT -> Forecaster handoff;
- existing output schemas unless a new continuation receipt requires an additive field/artifact;
- existing keyless packet preparation and answer-wall concepts;
- existing 1,940-path / 46-block capability surface;
- current permanent Frankie/core/provider files remain untouched.

The old reduced-surface workflow remains historical evidence only. Do not mutate it into the new experiment.

## Canonical evidence

Only these native source identities are eligible:

- `glbx-mdp3-20211001.mbo.dbn.zst` — warmup/development
- `glbx-mdp3-20211003.mbo.dbn.zst` — warmup/development
- `glbx-mdp3-20211004.mbo.dbn.zst` — held-out blind
- `glbx-mdp3-20211005.mbo.dbn.zst` — held-out blind

The exact SHA-256, bytes, and native MBO record count of each file must be bound by a frozen source manifest before launch.

Forbidden as benchmark market input:

- the prior reduced seconds surface;
- `V4_NATIVE_FULL_MBO_SECONDS.jsonl.gz`;
- MBP/top-10 as a substitute for MBO;
- Step-1 event/evidence/proposal/self-fit/self-score artifacts;
- Step-1 typed state or answer-bearing derivatives;
- any result/reveal/outcome surface.

`ts_recv_ns` is the causal availability clock. `ts_event_ns` remains exchange event time only.

## Lossless stream serialization

### Fundamental rule

Every normalized native MBO action crosses each Frankie's market-evidence boundary exactly once and in causal receive order.

A chunk may change *delivery size* only. It may not change scientific resolution.

### Event-group rule

The V4 adapter's completed `F_LAST` event group is the smallest legal chunk boundary.

Never split an open event group across two model calls or checkpoints.

Each emitted event-group record includes all normalized `raw_actions` from the native group. No raw action may be omitted because it does not affect top-of-book state.

### Chunk rule

Chunks are deterministic contiguous sequences of completed event groups. A chunk ends when the next complete event group would exceed a configured byte/token delivery cap or a configured maximum event-group count.

Chunking must be deterministic for the same source manifest + serializer version + chunk policy.

No semantic ranking, event selection, thresholding, anomaly filtering, strategy filtering, or model-guided skipping is allowed in the chunker.

### Full book / FIFO availability

The complete reconstructed order book and FIFO queues are not serialized redundantly after every raw action. Instead:

- exact full continuation state is stored at chunk boundaries;
- the chunk contains every intervening raw action needed to advance that state exactly;
- chunk-start and chunk-end adapter-state hashes bind the full order/FIFO state;
- an optional requested full-state view is materialized from that exact bound adapter state, never from Step-1 results.

This is lossless streaming, not data degradation: initial state + every ordered raw action + deterministic adapter semantics reproduce the exact ending full book/FIFO state.

## Role execution

### Real-Time Frankie

1. Start from the frozen warmup/held-out source manifest and legal initial adapter checkpoint.
2. Consume every raw-MBO chunk sequentially.
3. After each chunk, emit a bounded continuation object containing only its accumulated working hypotheses/state, uncertainty, open candidates, evidence references, and clocks needed to continue reasoning.
4. The continuation object is hashed/frozen before the next chunk.
5. The next chunk receives the prior validated continuation + the next exact raw-MBO chunk.
6. After the final held-out chunk, validate the existing RT output contract and freeze the authoritative RT state/first lock.

The continuation object is not a replacement for raw MBO and may not be used to skip unread chunks.

### Forecaster Frankie

Only after RT is frozen:

1. Bind the exact frozen RT state/hash.
2. Independently consume the same complete native raw-MBO stream in the same chunk order, with its own continuation objects.
3. It may use the frozen RT state but may not modify or reconstruct a competing RT current-state lock.
4. After the final chunk, validate and freeze the existing Forecaster output contract.

Both roles therefore receive the same full native market evidence. The Forecaster is not given a reduced substitute merely because RT already consumed the stream.

## Clean versus memory-assisted conditions

### CLEAN

Exclude all Oct-4/5-specific conclusions, hypotheses, event discoveries, strategy ideas, correlations, clocks, or output artifacts generated by the earlier reduced/non-full-MBO two-day run.

Frankie's general pre-existing brain/capability knowledge remains available subject to its existing authority rules.

### MEMORY_ASSISTED

Add only Frankie's own unrevealed Oct-4/5 knowledge from the prior reduced-surface run:

- model-generated hypotheses;
- correlations noticed;
- clocks/relationships worth revisiting;
- uncertainties/contradictions;
- things Frankie wanted richer data to resolve;
- methodological lessons formed without an answer reveal.

Still forbidden:

- Step-1-derived information;
- realized outcomes used as answers;
- scores/reconciliation;
- post-reveal hindsight;
- current clean-run outputs;
- outputs from another benchmark controller.

The exact memory bundle must be hash-bound and audited before the memory-assisted run.

## Checkpoint/restart contract

Every role/condition uses restart-safe interval saves.

Mandatory saves:

- configurable completed-event-group intervals;
- every raw DBN file boundary;
- immediately before every expensive model call;
- immediately after every accepted model response;
- RT final freeze;
- Forecaster final freeze;
- final arm lock.

A restart restores:

- exact source manifest;
- source file/cursor and completed raw-MBO record count;
- exact V4 full order/FIFO/rolling-state continuation;
- current chunk identity;
- validated role continuation state/output hashes;
- prior checkpoint hash chain;
- next legal action.

Resume must fail closed on source, code, serializer, controller, memory-mode, or checkpoint-chain drift.

## Progress probe

Progress is derived from actual hash-bound native MBO record counts, not wall time.

At minimum expose:

- controller/arm;
- CLEAN or MEMORY_ASSISTED;
- role (RT/Forecaster);
- phase;
- current source DBN/date;
- completed native MBO records;
- total declared native MBO records;
- exact percentage;
- completed event groups;
- current/last `ts_recv_ns`;
- latest checkpoint sequence/hash/path;
- last accepted model-call checkpoint;
- CPU/RAM/swap operational state where available;
- frozen outputs already completed;
- next resume action.

The probe must not print Step-1 scientific results.

## Eight-arm reveal gate

This Chat-side spec supplies A-clean and A-memory. The paired BOSS branch supplies B0/B1/B2 clean/memory arms.

Step-1 remains sealed until all eight required final arm locks verify:

- A-clean
- A-memory
- B0-clean
- B0-memory
- B1-clean
- B1-memory
- B2-clean
- B2-memory

No current-arm output may be fed into another current arm before the reveal gate.

Only after all eight locks may Step-1 be opened once for reconciliation/scoring.

## Testing strategy

TDD increments:

1. **Raw event-group serialization RED/GREEN**
   - all raw actions preserved byte-for-byte at normalized-field level;
   - receive order preserved;
   - `F_LAST` chunk boundaries only;
   - deterministic chunk hashes;
   - no seconds/Step-1 field accepted.

2. **Chunk reconstruction RED/GREEN**
   - continuous adapter replay equals chunk-by-chunk replay;
   - chunk-start + raw actions reconstruct exact chunk-end adapter state;
   - no event/action duplication or omission across chunks.

3. **Role continuation RED/GREEN**
   - continuation state is immutable/hash-bound;
   - next chunk cannot run without prior accepted continuation;
   - clean/memory mode cannot drift;
   - final role output freezes before next authority stage.

4. **Memory boundary RED/GREEN**
   - clean condition rejects prior Oct-4/5 run artifacts;
   - memory condition accepts only allowlisted unrevealed prior-run artifacts;
   - Step-1/reveal/post-reveal sources fail closed in both.

5. **Brownfield preservation**
   - existing coordinator output/first-lock validation retained;
   - 1,940 paths / 46 blocks preserved;
   - permanent Frankie/core/provider files unchanged.

## Success criteria before launch

- real raw source manifest/count receipt exists after the Step-1 host is free;
- lossless chunk tests pass;
- exact adapter resume tests pass;
- clean/memory knowledge gates pass;
- progress probe is real record-count based;
- provider/model call budget is bounded and checkpointed;
- no Step-1 answer-bearing path can cross the evidence boundary;
- A-clean launcher requires explicit authorization and does not auto-launch on code push.
