# The agent program: what is built and how to use it

Built in the twenty-first session (2026-11-24) from the plan
`research/kalshi/frankie_boss/CLAUDE_ARCH_PLAN_GRAPH_ENGINEERING_ADOPTION_20261123.md`. Code is here in
Markets `tools/`; every record it writes is in a `DavisAI1974/markets-data` checkout (`graph/`,
`experiments/`), found beside this checkout or through `MARKETS_DATA` or `--data`.

Nothing here changes Frankie, Granite or a calculation. Nothing here is switched on for Frankie.

## Start a session from the graph (stage 5a)

```
python3 -m tools.kgraph.context --budget 6000                      # what a new session needs first
python3 -m tools.kgraph.context --budget 4000 --task "<the task>"   # the claims about what the task names
```

Every line ends with its claim id, its file and line, who said it and when. The last section says what
is NOT in the text (what fell under the budget, what has something against it, documents not read yet).
Tokens are estimated at 4 characters a token.

## What needs Greg's go (nothing below is run by building it)

| What | Why | How it is held |
|---|---|---|
| A run of the swarm (stage 6) | model tokens at scale | `tools.swarm.run go` refuses without `--greg-go "<his words>"` |
| A run of the token test (stage 8) | model tokens at scale; needs Granite's receipts | `tools.token_test.replay go` refuses without `--greg-go` |
| Switching Frankie's input to `graph_v1` (stage 5b) | changes Frankie | nothing of Frankie calls `tools.kgraph.packet` |
| Dispatching a loop on a runner or a pod (stage 3) | HOLD | the harness runs only where it is called; there is no workflow file |
| Reading the 99 documents not read yet into claims | model tokens at scale | `tools.kgraph.extract coverage` lists them |
| Any paper run | his rule | not part of this code |

## The stages

| Stage | Code | Command |
|---|---|---|
| 2. The experiment record | `tools/exp_dag.py` | `python3 -m tools.exp_dag log | leaves | fetch <id> | children <id> | lineage <id> | diff <a> <b> | push ... | set-status ... | rebuild` |
| 3. The keep-if-better loop | `tools/ratchet/` | `python3 -m tools.ratchet.loop --program <program.md> --replay <commit> ... --scratch <dir>`; control files in `tools/ratchet/programs/`, the fields in `PROGRAM_TEMPLATE.md` |
| 4a. The graph's layout and store | `tools/kgraph/schema.py`, `store.py`, `sources.py` | `python3 -m tools.kgraph check | counts | manifest` |
| 4b. Filling it, no model | `ingest_agent_runs.py`, `ingest_det.py`, `ingest_paper.py`, `rule_versions.py` | `python3 -m tools.kgraph.ingest_det` (trade days, manifests, ROOT calc receipts, dipole events, peaks, renders) and the others the same way |
| 4b. Reading documents into claims | `extract.py` | `plan`, `prompt --doc <repo>:<path>[#L<a>-L<b>] --out brief.txt`, `load --result returned.json --run run:00NN`, `coverage` |
| 4b. Merging names | `resolve.py` | `rules`, `candidates --out brief.txt`, `apply --merges m.json --run run:00NN`, `undo --edge e:... --reason ... --run ...` |
| 4c. The grounding check | `grounding.py` | `claim <id>`, `text "<sentence>"`, `node <id>`, `all [--record]` |
| 5a. Session context | `context.py` | above |
| 5b. Frankie's packet from the graph | `packet.py` | `python3 -m tools.kgraph.packet --event dipole:<id> --budget 4000 [--json]` |
| 6. The swarm | `tools/swarm/` | `python3 -m tools.swarm.run plan ...` (no model call), `go ...` (needs his go) |
| 7d. The paper record in the graph | `ingest_paper.py` | `python3 -m tools.kgraph.ingest_paper --platform <paper-trading-platform checkout>` |
| 7f. Rule versions | `rule_versions.py` | `load`, `check [--record]` |
| 8. The token test | `tools/token_test/` | `python3 -m tools.token_test.replay plan ...` (no message sent), `go ...` (needs his go) |

## The rules the code holds itself to

- NOTHING IS REPLACED (Greg, 2026-11-24). A trial that did not improve, a claim a later claim speaks against,
  a rule version, a merge taken back: each stays on record with what was found about it. What does not hold up
  is marked or scored and is called last or not called; it is never dropped because something later exists.
- No new claim is tied to a tastytrade platform issue (Greg, 2026-11-24): `tools/kgraph/platform_scope.py`.
- The record is lines, only ever added to. A changed line is its next revision; a link taken back is a
  new line marked withdrawn. `python3 -m tools.kgraph check` lists every breach of a write rule.
- A claim has a source or is marked as an inference. A claim read by a model is written only when its
  quote stands in the file word for word; one that does not is kept as a Task line, not believed.
- One file, one id (`src:<repo>:<path>`). A trade day is 6 pm Eastern the evening before to 5 pm Eastern
  on the named date; a file cut on a UTC clock day keeps `utc_day` and is never called a trade day.
- No mid price is ever stored (`schema.check_node` refuses it). No trade cost enters anything.
- Nothing is averaged, pooled, ranked or labelled. Each trial, claim, order and fill is its own line.
- A reverted or crashed trial, a claim under a cutoff and a merge under a cutoff are all kept.
- Checks read real records (`tests/agent_program/`, skipped with the reason when a checkout is missing):
  `python3 -m pytest tests/agent_program -q`.

## A new reader's run, step by step (stage 4b)

1. `python3 -m tools.kgraph.extract prompt --doc markets-data:<path> --out brief.txt`
2. Give `brief.txt` to the reader (the scout on Haiku in the plan). It returns JSON.
3. Add the run to `paper-trading-20261123/agent-runs.jsonl`, keep the JSON under `graph/reads/`, commit.
4. `python3 -m tools.kgraph.ingest_agent_runs`, then
   `python3 -m tools.kgraph.extract load --result graph/reads/<file> --run run:00NN`
5. `python3 -m tools.kgraph.extract coverage` and `python3 -m tools.kgraph check`
