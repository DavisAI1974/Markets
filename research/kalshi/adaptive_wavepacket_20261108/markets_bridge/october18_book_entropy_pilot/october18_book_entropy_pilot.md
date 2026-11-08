# October 18 paired NG book entropy pilot

Input is the archived October 18, 2023 native book sequence for instrument 150611 and the existing early falling-touch replay ledger. The flow archive contains at most six consecutive saved seconds in or immediately before this window, so this experiment uses displayed touch sizes from the verified book sequence. It exercises the wavepacket engine's fixed-bin feature extractor. The full flow-based coupling and Level 2 fits have a separate input requirement.

The first 92 disjoint blocks of 60 consecutive native group closes set the bins. Subsequent features use disjoint blocks of 60 groups. At each baseline signal, use only the two latest complete post-calibration blocks known by that signal's original nanosecond clock and cursor. The overlay admits the same signal and direction if entropy of the displayed size on its side declines. This is an exploratory timing condition. No trade direction or exit is learned from the replay outcomes.

The ledger records all 2,850 baseline signals, including 719 calibration-period signals, six awaiting a second complete block and 204 with review-required inputs. Twenty of 277 post-calibration blocks required review. Source evidence, prior and latest feature endpoints, quote outcomes and censoring remain available per signal. The final 54 groups stay in the source and have no completed 60-group feature. Outcome counts below use the original 1 ms entry eligibility and the original midpoint outcomes. A midpoint outcome measures direction. Paper execution is a separate verification step.

| Side and horizon | Baseline on common support, agree / oppose / flat / censored | With entropy decline, agree / oppose / flat / censored |
| --- | --- | --- |
| Ask, 1 s | 330 / 265 / 395 / 0 | 173 / 123 / 224 / 0 |
| Ask, 5 s | 400 / 389 / 189 / 12 | 220 / 197 / 95 / 8 |
| Ask, 30 s | 307 / 525 / 103 / 55 | 171 / 256 / 62 / 31 |
| Bid, 1 s | 268 / 262 / 401 / 0 | 119 / 133 / 201 / 0 |
| Bid, 5 s | 367 / 358 / 201 / 5 | 158 / 187 / 106 / 2 |
| Bid, 30 s | 515 / 282 / 100 / 34 | 226 / 153 / 54 / 20 |

Common support is all 990 ask and 931 bid signals where the overlay could make a decision. The filtered arm takes 520 ask and 453 bid signals. It keeps the baseline outcomes of skipped observations in the source-linked ledger. Signals overlap, share book features and come from one previously studied session. These counts are descriptive. The ask-side five-second observation warrants a paper test alongside the baseline. The bid-side deterioration and adverse ask-side 30-second results remain part of the finding. Status is `NOT_ENOUGH_INFO`.

Reproduction: at the Markets root, add the adaptive wavepacket `working_tree` to `PYTHONPATH` and run `python -m research.kalshi.adaptive_wavepacket_20261108.markets_bridge.october18_book_entropy_pilot <new-output.jsonl.gz>`. Standard output is the JSON summary. The source hashes in that summary pin the exact real inputs.
