# October 18 filter stacking check

All four arms start with the same early falling-touch rule and retain its side, native signal coordinates, 1 ms entry eligibility, and original midpoint outcomes at 1, 5 and 30 seconds.

1. Baseline only.
2. Baseline plus declining same-side touch-size entropy.
3. Baseline plus at least one original print recorded in the signal group by its close.
4. Baseline plus both conditions.

The same-group print is a time and membership condition. It supplies no aggressor label. The runner checks every linked print against instrument, source line, native cursor and availability. For the four-way comparison, common support is the 990 ask and 931 bid signals with a usable entropy decision. The receipt also reports baseline and print-only results on all 2,850 signals. The ledger retains each signal, eligibility for every arm, and outcomes including censored cases.

| Side and horizon | Baseline | Entropy | Same-group print | Both |
| --- | ---: | ---: | ---: | ---: |
| Ask, 1 s | 330 / 265 / 395 / 0 | 173 / 123 / 224 / 0 | 50 / 26 / 35 / 0 | 27 / 11 / 21 / 0 |
| Ask, 5 s | 400 / 389 / 189 / 12 | 220 / 197 / 95 / 8 | 46 / 47 / 18 / 0 | 24 / 25 / 10 / 0 |
| Ask, 30 s | 307 / 525 / 103 / 55 | 171 / 256 / 62 / 31 | 34 / 59 / 16 / 2 | 22 / 29 / 8 / 0 |
| Bid, 1 s | 268 / 262 / 401 / 0 | 119 / 133 / 201 / 0 | 38 / 22 / 36 / 0 | 19 / 11 / 20 / 0 |
| Bid, 5 s | 367 / 358 / 201 / 5 | 158 / 187 / 106 / 2 | 45 / 33 / 17 / 1 | 21 / 19 / 10 / 0 |
| Bid, 30 s | 515 / 282 / 100 / 34 | 226 / 153 / 54 / 20 | 52 / 34 / 9 / 1 | 26 / 19 / 5 / 0 |

Counts are agree / oppose / flat / censored. On the ask at 1 s, the stack is a narrower cohort with 27 agreements and 11 opposing moves. On the bid at 1 s, the stack keeps exactly half the print-only agreements and opposing moves. At 5 s the stack has one more opposing move than agreement on the ask and a narrower agreement margin on the bid than the print-only arm. These are overlapping observations from a single day. Keep every arm eligible for paper discovery and use occurrence count to schedule trials. Status remains `NOT_ENOUGH_INFO`.

Reproduce from the Markets root with `python -m research.kalshi.adaptive_wavepacket_20261108.markets_bridge.october18_stack <new-ledger.jsonl.gz>`. The stdout receipt records the three source hashes. The resulting trade outcomes are historical midpoint movements.
