# Frankie run findings ledger (operator-recorded; never hidden from Frankie)

Greg Davis, 2026-09-20: "we will make this info available to Frankie going forward on the Sunday runs
and all subsequent calc findings. We will not hide this." This file is appended, never rewritten, and
its exact bytes are rendered into Frankie's prompt on every cycle that renders a prompt, witnessed in
the request attachment (`run_findings_witness`). Entries are dated, name their evidence (run ids,
hashes, receipts), and distinguish what was observed from what was concluded. Frankie's own prior
lessons (the `lessons` store) are rendered beside this ledger, so nothing he wrote is hidden from him
either.

## 2026-09-20: launch day, the 20211003 two-cycle run (day 20211003, cycles 2)

Observed, cycle 0, machine side (retained on the host in `actual-feedback-run/execution/cycle-00`):
- The native calculation ran at 15:45-15:56Z on the source prefix (57,027 records, 3,262 rows in the
  packet). One forecast record: group A_MEMORY, disposition ABSTAIN, guessed net USD -0.009, overnight
  gap +0.006, a flat `path_p50_curve` around 18.0001 (level units as served), confidence null. Native
  checkpoint count 2, head 3b111695.
- The Granite critic (131,072 context; input 92,439 tokens; output budget 38,633) returned in 124
  tokens: `evidence_refs` [], `contradictions` [], `missing_evidence` [], `hypotheses` [], verdict
  CONSISTENT, `finish_reason: stop`. The contract requires 1..4 hypotheses, so the critic was recorded
  as rejected and the controller result is `incomplete` (stage `controller` 51698a32, request hash
  81d53453). The coordinator continues on `incomplete`; whether an empty critique is the expected
  behaviour on this packet or a prompt/packet issue is an open science question.
- The causal handoff export (18 sections) is hash-verified (stage `export` 7afd5c6a); the durable
  principal request was written at 16:39:23Z (`session-request.json`, 14,909,376 bytes, sha256
  e0c461d7...; `prompt.md` 28,294,692 bytes, sha256 58a96207...).
- Provenance overrides, each receipted, nothing deleted: the retained run directory was code-bound to
  an earlier checkout and superseded (moved aside); CRLF on the Windows host re-minted every
  source-hashed identity and the checkout was normalized to LF; the two-cycle prefix batch was rebuilt
  (prefix data byte-identical, code pins moved); the cycle identity supersede accepted code hash
  61b761c8 -> a019bb8d and arm 3a85e8bd -> 2cf7c9e2; the export manifest's `boss_commit` pin
  34a4feac -> 2b069fc2 was accepted against the declaration.

Observed, cycle 0, Frankie side:
- The principal session (Root) did not run on the retained request when first reported: the request
  and prompt existed only on the host, which the session could not see, and its reports of recording,
  pushing and a pull request were not verifiable and turned out not to have happened. The request was
  exported unchanged to a private staging prefix at 21:34Z (run 35539110298) and the session was
  re-issued with a written task. Until it records, nothing after it has run: verify, native learning,
  checkpoint readback, completion, the classroom correction turn.

Concluded (operator): a cycle's machine result can exist and be retained while the learning from it
has not happened; the two are separate facts and both are recorded here. The empty critique is a
finding to be explained, not an error to be hidden.

## 2026-09-20, standing rule restated by Greg Davis: the calculations are Frankie's, not the runner's

"The calcs are not for runners to do. Frankie needs to be learning from these. This is something we have
covered over and over." Measured against the registry of the August 28 A_MEMORY recalculation (run
33746436209; crosswalk audit of 2026-09-16): all 77 applicable input layers were delivered to Frankie
(chains with extensions, reappearances and ancestry; D structures and families; dipoles and geometry; pair
and triplet recurrence; pre-birth opportunity; order lifecycle; full-book FIFO queue; microstructure;
derived geometry), and the ten append-only OUTPUT ledgers registered for Frankie were OUTPUT_PENDING with
none filed, in the first Sunday run as well. From this cycle on the request instruction states the rule
and names the ten ledgers; they are filed as lesson entries and rendered back to Frankie every later cycle.

## 2026-09-20, the required calculation set is the registry itself, not a summary of it

Greg Davis: "frankie (errantly) didn't do the aug calcs but the correct ones were done so don't look at who
did them but look at the ones that were done." The set that was done is the native ingestion registry of
the August 28 A_MEMORY recalculation (registry sha256 239a1480..., crosswalk of run 33746436209 on
2026-09-16): 49 calculation layers in seven groups (order_lifecycle 9, full_book_fifo_queue 8,
microstructure_mechanics 7, legacy_observable_crosswalk 5, derived_geometry 8, prebirth_opportunity 5,
causal_clocks 7), compared against the nine frozen learned-structure layers. From this cycle on the request
instruction names every layer verbatim and requires one `calculation_accounting` lesson entry giving each
layer's status (derived, compared, could_not with reason); the constant is tested against the crosswalk
file so it cannot drift from the registry. Cycle 0's request is re-rendered under this instruction.

## 2026-09-20, cycle 0 is re-run WHOLE, from the beginning, not in steps (Greg Davis)

"It feels like we are skipping steps doing things this way which is why i wanted a full rerun from the
beginning and not steps." The re-issue built earlier today kept the machine half of cycle 0 (the native BOSS
ABSTAIN, the empty Granite critique, the export) and re-rendered only Frankie's request; that was piecewise
and it was stopped before it produced a request. Recorded for the record: the cycle's order is fixed and
sequential (native BOSS and Granite critic, then the export into Frankie's package, then Frankie's session
with the same-session classroom teach-back and correction, then native learning, readback, completion);
nothing on the machine computes exhaustion chains, D structures or families; those derivations, and the
classroom, are Frankie's step, and he correlates the machine's result after it is delivered to him, never
concurrently. The whole cycle is superseded with receipts (nothing deleted) and runs again under the current
code so his request carries a fresh machine result and the classroom runs anew.
