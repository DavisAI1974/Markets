# Frankie NG Exhaustion Blind Protocol Blocker — 2026-08-16

Status: **FAIL_CLOSED_BEFORE_PREDICTION**

This checkpoint records a blind-protocol invariant failure discovered before any held-out price/outcome was opened. No blind prediction artifact has been generated, scored, or frozen because doing so without the missing frozen parameter would change the preregistered experiment.

## Canonical state at blocker

- Repository: `DavisAI1974/Markets`
- Scratch branch: `chatgpt/ng-exhaustion-frankie-blind-20260816`
- Frozen source HEAD before this audit commit: `27f0530aa05248a4dc90e758e5baab5a9bfa0f10`
- Permanent Frankie/runtime/workflow: untouched
- Held-out price/outcome: **NOT ACCESSED**
- Reveal artifact: **NOT REOPENED**

## Blind input integrity

The already-produced key-safe blind workflow artifact was used only to verify the model-facing blind input contract.

- Workflow run: `31985532223`
- Artifact ID: `9273678889`
- Artifact digest: `sha256:0c8e6ddd65213b8616ffdeaacebcb059d5e5d02eb4ca1e03f47d5653abb1b53e`
- Blind records: `1711`
  - A: `1616`
  - B: `35`
  - C: `60`
- Target-day brain entries redacted: `64`
- Brain leak scan: `PASS`
- Record leak scan: `PASS`
- Brain source mutation: none

Safe served-file SHA256 values:

- `ng_frankie_blind_records.json`: `38b6ea32cb55fc4464e2080050515764c54864f405b19411c115d39d866efc6f`
- `ng_frankie_blind_full_brain_redacted.json`: `2d9db5dd6ddbc05113dbfadf4fcb89e0d1ec601809cf7fd48fa6e344157a5953`
- `ng_frankie_blind_prompt.txt`: `3b3a105a2dc481115860496fc12426cd1b4f42991dd2aee638b4d1a675fad8a5`
- `ng_frankie_blind_manifest.json`: `2d2ec9d41c519af863344bdb779cf03848b850c7a1a297dc4b5b8d12cfac3ceb`

## Blocking invariant

The frozen reveal memo requires the primary A-family blind state assignment to use the **nearest revealed A post-dipole centroid using only dipole/exhaustion geometry** and explicitly forbids holdout retuning.

The allowed learned context for blind is limited by `FRANKIE_NG_EXHAUSTION_BLIND_KICKOFF_20260816.md` to the three frozen reveal/reflection/crosswalk documents; it explicitly says not to reopen the reveal packet to learn new rules.

Those allowed frozen documents preserve the qualitative A post-state geometry and reveal counts:

- `A-fast-collapse`: reveal n=822; falls through zero around the first 20–30 seconds.
- `A-persistent`: reveal n=797; remains strongly positive through that window and materially positive at +60 seconds.

However, the exact numeric centroid vectors (or an equivalent fully deterministic frozen state-assignment classifier/threshold) were not serialized in the allowed frozen context or the sealed blind input contract.

Therefore the required held-out A state cannot be assigned exactly under the preregistered rule without introducing a new choice.

## Disallowed alternatives

The following were deliberately **not** performed:

1. Refit K=2 or any state classifier on held-out curves. That would violate the frozen no-retuning rule.
2. Invent a zero-crossing or +20/+60 threshold from the qualitative memo. That would replace the frozen nearest-centroid rule with a new classifier.
3. Reopen/recompute from the reveal packet to recover the centroids. The blind kickoff explicitly forbids reopening reveal to learn/rederive rules after freeze.
4. Generate family-only or approximate predictions and call them the preregistered Frankie blind pass. The frozen memo says family x post-state is the primary test.
5. Access any held-out price/outcome, duration, displacement, ZigZag, realized-direction, or answer artifact.

## Resolution required before legal blind prediction

A legal continuation requires recovering an **already-frozen, pre-blind** representation of the revealed A post-dipole centroid vectors or an exact deterministic equivalent whose provenance predates held-out inspection and does not require reopening reveal to make a new modeling choice.

If no such pre-existing representation exists, this particular nearest-centroid blind test is methodologically incomplete and should remain failed closed rather than be repaired after the blind boundary.

## Integrity assertion

At this checkpoint:

- held-out identities/context were available only through the price-free blind artifact;
- held-out price/outcomes remain sealed;
- no scoring has occurred;
- no prediction has been generated under an approximate substitute;
- no Frankie brain/schema/roles/plays/datapoints/spawn.py/permanent workflow was modified.

This file is an audit checkpoint only. It is **not** a prediction freeze and does not authorize reveal/scoring.