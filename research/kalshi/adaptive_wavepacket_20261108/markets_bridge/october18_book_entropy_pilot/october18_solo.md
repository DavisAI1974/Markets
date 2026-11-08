# October 18 standalone condition checks

The original early falling-touch rule, entropy decline, and a directional print condition each have a standalone reading. The companion four-arm stack study answers a different question on common support: what happens when entropy and same-group print presence independently or jointly qualify falling-touch signals.

- Falling touch alone is the original replay across all 2,850 qualifying signals. Use its preserved ledger and the ALL / BASELINE results in the stacking receipt.
- Entropy alone fires at the close of each eligible 60-group block where same-side touch-size entropy fell relative to the preceding block. A bid-side decline calls short. An ask-side decline calls long. Bins come from the same 92 calibration blocks. Every block-side disposition is retained.
- Print alone evaluates each native group that contains recorded prints. All prints at the previous completed ask call long. All prints at the previous completed bid call short. Other groups remain ambiguous, including groups with prints on both sides or away from the prior touch. This is a direction convention based on price and the prior quote. It supplies no verified aggressor identity. The filter in the stack uses any eligible same-group print because the baseline already supplies direction.

The standalone runs use 1 ms entry eligibility and the first later completed book at least 1, 5 or 30 seconds after entry, scored at the midpoint. They preserve every source-linked decision and all outcomes, with no fee or fill model. The standalone rules can fire on different native groups. Their counts measure their own opportunity sets. Use the common-support stack results for a direct filter comparison on the same baseline opportunities.

| Rule and side | 1 s | 5 s | 30 s |
| --- | ---: | ---: | ---: |
| Falling touch, ask | 483 / 397 / 532 / 0 | 568 / 592 / 238 / 14 | 516 / 698 / 130 / 68 |
| Falling touch, bid | 422 / 450 / 566 / 0 | 606 / 545 / 282 / 5 | 712 / 537 / 148 / 41 |
| Entropy, ask | 43 / 40 / 49 / 0 | 54 / 49 / 28 / 1 | 45 / 68 / 13 / 6 |
| Entropy, bid | 29 / 39 / 57 / 0 | 45 / 51 / 28 / 1 | 60 / 47 / 13 / 5 |
| Print, ask | 229 / 195 / 191 / 0 | 256 / 272 / 85 / 2 | 229 / 317 / 51 / 18 |
| Print, bid | 198 / 177 / 167 / 2 | 240 / 222 / 79 / 3 | 278 / 215 / 39 / 12 |

Each cell is agreements / opposing / flat / censored. The 81 ambiguous print groups are preserved and have no directional score. This one previously studied window supplies observations for discovery. All individual and stacked variants remain eligible for paper, with status `NOT_ENOUGH_INFO`.

From the Markets root, add the component's `working_tree` to `PYTHONPATH` and run `python -m research.kalshi.adaptive_wavepacket_20261108.markets_bridge.october18_solo <new-ledger.jsonl.gz>`. The stdout receipt pins the input hashes.
