# NG Exhaustion Chain Phase 2 — Parallel Recurrence Reconciliation — 2026-08-18

Status: **LOCAL FOUR-LANE RECONCILIATION COMPLETE; GITHUB MATRIX LAUNCHED; NO PLAY PROMOTION.**

Runner: `research/ng_exhaustion_chain_phase2_parallel_agents_20260818.py` (commit `b6d3433214d59bd8b04b579fb53e868749b4ed05`).

Workflow: `.github/workflows/ng_exhaustion_chain_phase2_parallel_recurrence_20260818.yml` (launch commit `85c898440c27d0a82bfd6da2f31d21c1200cab5d`).

Each lane independently consumes the same immutable artifact set and the workflow verifies the downloaded ZIP SHA256 before computation:

- base54 canonical artifact `9281733364`, SHA256 `f50eaf74a57654334691cbf5cce3b038443f6944a9c00eb5da6ca35b557802b1`;
- held canonical artifact `9281272840`, SHA256 `21577d01d45241264df714ab6ee5b95f6a774e1475e0d74a9454221fdfdde12e`;
- Phase-1 lineage artifact `9289929292`, SHA256 `a67caab9de6b183e8c102ebd73a7e542aa909e23f66575290563e40b056efd95`;
- final 55W reconciliation artifact `9306082330`, SHA256 `f17c130df029429bfbc35067d1cc9d16128ca4fb227dd37f3fb4fbb8bbaf8875`.

The four lane contracts are: pair/triplet recurrence, D1->D2 extension propensity, D2/D3 timing families, and causal true/false-context investigator.

## Local reconciliation results

The four lane contracts were also executed locally against the hash-verified artifact copies while the GitHub matrix was launched.

### Pair/triplet recurrence lane

Top reusable strict-D2+ pair modules reproduce the richer atlas exactly: `PP|S` 291 pre-held / 38 held, `PO|S` 145 / 32, `OO|F` 143 / 23, `OP|F` 138 / 28, `XP|F` 132 / 20, and `SS|S` 124 / 18.

Top triplets also reproduce: `PPP|SS` 87 pre-held / 13 held, `PPX|SS` 40 / 11, `OOO|FF` 27 / 1, `PPS|SS` 27 / 2, and `POP|SF` 23 / 6.

### Extension lane

`PP|S` again exceeds the D1->D2 block baseline in every block: lift 1.27x / 1.22x / 1.29x / 1.20x (Eras 1-3 / Eras 4-5 / confirmation / held).

`OP|F` reproduces the investigator pattern: lift 1.21x / 1.33x / 1.20x pre-held, but 0.73x held. It is preserved for decomposition rather than killed.

### Timing lane

Exact D2 reproduces the three pre-held timing centers `126.25s / 215.19s / 797.96s`; pre-held counts `947 / 380 / 52`; held assignments `156 / 52 / 5`.

Exact D3 reproduces the two-family centers `210.51s / 609.34s`; pre-held counts `83 / 10`; held assignments `25 / 6`.

### Investigator lane

The sign-changing motifs reproduce, including `O -> FLIP` (+0.058t / +0.030t / +0.120t pre-held, held -0.477t), `P -> FLIP` (+0.191t / +0.323t / +0.161t, held -0.818t), `OOO -> FLIP` (+0.082t / +0.065t / +0.146t, held -0.769t), and `OOSS -> SAME` (+0.097t / +0.064t / +0.200t, held -1.385t).

The lane policy is explicitly `FLAG_AND_DECOMPOSE_NOT_AUTO_KILL`.

## Boundary

The local four-lane results agree with the richer post-exit/recurrence and timing/context findings. The GitHub matrix has been launched for durable independent artifacts, but this document does not claim its workflow conclusion until that run is retrieved and verified.

No frozen detector, canonical row, runway-clock file, permanent Frankie file, Frankie 1 file, protected spawn file, or frozen SSOS paper-play rule was modified.
