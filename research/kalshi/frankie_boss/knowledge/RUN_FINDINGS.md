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
