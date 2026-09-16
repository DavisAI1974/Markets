# ccode handoff — final Dipole classroom review (2026-09-16)

Repository: `DavisAI1974/Markets`

Branch: `chatgpt/frankie-dipole-classroom-20260916`

Reviewed ccode base already fast-forwarded earlier: `f6f3787f1b7f7c304d09f82c54905e7065ba5110`.

ChatGPT hardening commits after that review:

- `38b90e16149e15fa5462f54b20378c04a9955183` — harden answer-key/correction boundary.
- `0797d54f3b5729ac89e89f821af32e33d13b6702` — add non-punitive novelty investigation and instance-level evidence review.

The documentation commit containing this handoff is intentionally not part of the code-review range above.

## Greg's governing classroom rule

Complete Dipole coverage is invariant; only who does the explaining changes. Dipole begins as an exhaustive teacher. Every cycle still accounts for all 19 Dipole dimensions and the complete 171-pair surface. Dipole may back away only as Frankie demonstrates mastery, and the teaching level may regress when mastery degrades.

New ruling added after your previous review:

1. Frankie must have a protected path to find something new or innovative beyond what Dipole explicitly taught.
2. A novel Frankie hypothesis is **not** a classroom error merely because it is outside Dipole's curriculum.
3. Dipole must investigate the causal evidence Frankie cites before responding to a new idea.
4. Greg does not want Dipole saying a premise is "wrong." When a factual subclaim conflicts with the governed evidence, Dipole should say **"the data is showing this instead"** and identify the exact observation, state/value, direction, or pair that differs.
5. A contradiction applies only to the specific contradicted instance/subclaim. Do **not** reject the broader premise unless separate evidence actually contradicts the broader premise.
6. Findings outside the Dipole fact key (for example a broader FIFO/full-book interaction) remain hypotheses/not-yet-testable rather than being rejected.

## What changed in `38b90e1`

Three files relative to `f6f3787f`:

- `research/kalshi/frankie_boss/dipole_classroom_hardening.py`
- `research/kalshi/frankie_boss/operations/run_actual_sunday_classroom.py`
- `research/kalshi/frankie_boss/tests/test_dipole_classroom_hardening.py`

Intent:

- same-session correction no longer sends the complete host post-grade / 19+171 answer key;
- next-cycle pre-message carries only a compact prior-correction summary;
- taper regresses one level after a non-mastered cycle;
- Pearson is suppressed below 8 overlapping PRESENT observations;
- duplicate teacher-key audit copy is removed from the principal directory; host-owned cycle copy remains;
- production classroom wrapper routes through the hardened layer, leaving the lawful `run_actual_sunday.py` untouched.

## What changed in `0797d54`

Three files relative to `38b90e1`:

- `research/kalshi/frankie_boss/dipole_classroom_final_review.py` (new)
- `research/kalshi/frankie_boss/operations/run_actual_sunday_classroom.py` (routes through final layer)
- `research/kalshi/frankie_boss/tests/test_dipole_classroom_final_review.py` (new focused tests)

### Protected innovation path

The initial Frankie response now also carries `dipole_novel_findings` (empty list allowed). A novel finding includes a premise, why Frankie believes it is novel, and one or more causal evidence references. Evidence references can be:

- exact Dipole observation;
- exact Dipole pair relationship;
- other causal evidence outside the Dipole fact key.

Dipole's deterministic investigation checks only what the classroom can actually verify. The result is retained separately from classroom mastery. Novelty is never scored as a mastery failure merely for being new.

For an exact cited subclaim that differs from the current governed Dipole evidence, the teacher response is local: `the data is showing ... instead`, plus an explicit statement that the broader premise remains open.

Other causal evidence that this classroom cannot verify is retained as not-yet-testable / later-review evidence, not declared false.

### Discovery attribution

The model-visible record now distinguishes:

- TEACH / GUIDED: `INSTRUCTIONAL_COMPREHENSION`; not eligible to claim independent discovery.
- SOCRATIC / VERIFY: `INDEPENDENT_RECOGNITION_ELIGIBLE`.

The audit key object remains withheld in every mode, but the record no longer pretends TEACH exposure is independent discovery.

### Actual-exchange transcript

The readable transcript is now intended to contain only:

1. what Dipole actually taught before Frankie's answer;
2. Frankie's teach-back + exhaustive ledgers;
3. Frankie's novel findings;
4. the exact local data-review/novelty-investigation message sent back to Frankie;
5. Frankie's same-session corrected-understanding acknowledgement.

The complete host grade and teacher key remain retained audit evidence but are not printed into this classroom transcript. This fixes the mismatch found after `38b90e1`, where the Markdown renderer could reveal the full host grade even though Frankie did not receive it.

Narrative prose / novel hypotheses are explicitly retained but not deterministically scored as classroom mastery.

### Relationship duplicate cross-check

Frankie's optional per-component factual relationship statements are cross-checked against the mandatory canonical 171-pair ledger. `HYPOTHESIS` remains allowed as a separate hypothesis. Contradictory factual representations create a local reconciliation item instead of silently coexisting.

### Root-cause grouping

The full correction IDs remain auditable, but relationship/representation review items that mechanically derive from a component-direction miss are grouped under the component-direction root. One conceptual miss should not be interpreted as nineteen independent failures.

### Direction definition

The model-visible pre-message now says explicitly: graded direction is first PRESENT observation versus last PRESENT observation in the retained cycle window. Intrawindow rises/falls/reversals can exist even if the endpoint definition is FLAT.

### Cycle-count ownership

The final layer snapshots the teacher using `curriculum_cycle_count` derived by the wrapper from the retained runtime schedule. It no longer uses `len(COLUMNS)` as any cycle-count authority. Please inspect this carefully against the existing Sunday 19-cycle contract; the wrapper's request-search loop still intentionally scans the Sunday 19-cycle execution layout.

## Review requests for ccode

Please review specifically:

1. **No answer-key leak-back:** neither the same-session correction nor next-cycle pre-message should disclose the full prior grade/teacher key.
2. **Transcript fidelity:** `dipole-classroom-transcript.md` should contain only the actual model-visible teacher exchange + Frankie responses, not host-only full grade material.
3. **Novelty non-punitive behavior:** novel findings cannot lower mastery simply because they are novel/outside the curriculum.
4. **Granular contradiction rule:** when evidence differs, confirm the response names only the contradicted observation/pair/subclaim and says the data is showing X instead. Confirm it does not invalidate the whole premise by implication.
5. **Investigation before response:** exact Dipole evidence refs are checked before any difference statement. Evidence outside the fact key should remain unverified/not-yet-testable, not false.
6. **Discovery attribution:** only SOCRATIC/VERIFY should be eligible for independent-discovery labeling.
7. **Relationship cross-check:** factual component relationship claims and canonical 171-pair records cannot silently disagree; HYPOTHESIS is still distinct.
8. **Root-cause grouping:** derived pair misses should not inflate conceptual failure counts.
9. **Pearson floor:** no coefficient should be exposed below 8 overlapping PRESENT points; overlap count remains visible.
10. **Taper regression:** a non-mastered later-mode cycle backs the teacher up one level.
11. **Audit-key filesystem isolation:** no `dipole-classroom-teacher-key.audit.json` should be written in the principal/model-facing directory. Host cycle key remains retained.
12. **Schedule-bound snapshot:** inspect the new schedule-derived curriculum bound and make sure no accidental coupling remains between 19 Dipole columns and 19 Sunday cycles.
13. **No science drift:** confirm Dipole targets/teachers/normalisers, context session/cache, lawful host, base principal adapter, native model/training semantics, Frankie inputs/calculations/planes/adapters/replay/Memory A remain unchanged by these two commits.
14. **Wrapper seam:** the isolated branch still patches the principal adapter class at the classroom wrapper boundary. Decide whether to keep that isolated composition for now or replace it with an explicit merge-time composition seam.

## Tests / execution status

Your earlier review at `f6f3787f` had 42 focused tests green.

ChatGPT could not execute pytest for the two post-review hardening commits in its current environment. The new Python sources were syntax-checked before the GitHub writes, and the GitHub commit/file diff was inspected, but **do not treat the new focused tests as passed until you run them**.

Please run the prior classroom focused suites plus:

- `research/kalshi/frankie_boss/tests/test_dipole_classroom_hardening.py`
- `research/kalshi/frankie_boss/tests/test_dipole_classroom_final_review.py`

No Frankie, Granite, EC2, market-data, Pod, training, or result-bearing run was launched while making these changes. Launch gate remains closed.
