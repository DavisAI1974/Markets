# S116 Novel Edge Lab Addendum — Rule Canonicalizer Wired

This addendum supersedes the original handoff's statement that the Kalshi rule
canonicalizer was not built.

## Built after the original handoff

### `research/kalshi/kalshi_rule_canonicalizer.py`

A conservative, credential-free scanner that accepts a current Kalshi market JSON list
or an object containing a `markets` list.

It produces:

- normalized complete rule text;
- extracted strike;
- settlement/close time normalized to UTC when possible;
- verification source;
- source instrument;
- measured field;
- strict inequality class;
- `strict_hash` for exact normalized-rule review;
- `semantic_hash` for near-match discovery only;
- missing-field warnings;
- gross YES/NO pair checks before fees.

### Match discipline

- `strict_hash` groups may enter exact-payoff human review.
- `semantic_hash` groups are near-matches only and cannot be labeled arbitrage.
- A positive gross pair remains before fees, slippage, legging, dispute risk and
  execution failure.
- Complete current-rule human review remains mandatory.

### Dashboard diagnostic

The rank-1 duplicate-wrapper card reads:

```text
data/novel/kalshi_rule_scan.json
```

When present, the card displays:

- canonical market count;
- exact normalized-rule group count;
- semantic near-match count;
- gross positive pair count before fees.

When absent, it displays `AWAITING CURRENT MARKET JSON` and the generation command.

### Generation command

```bash
python research/kalshi/kalshi_rule_canonicalizer.py current_markets.json \
  --out data/novel/kalshi_rule_scan.json
```

### Self-test

```bash
python research/kalshi/kalshi_rule_canonicalizer.py --selftest
```

The synthetic test covers:

- two different wrappers with identical normalized rules and settlement identity;
- an apparent source mismatch that must not enter the exact group;
- cents and dollars price-schema normalization;
- one positive gross-before-fee cross-wrapper pair.

## Still open

The remaining top-card work is operational rather than conceptual:

1. fetch the complete current active-market objects and rules;
2. archive the market snapshot with receipt time and rule version;
3. run the scanner on a durable cadence;
4. capture synchronous executable YES/NO asks;
5. apply the current Kalshi fee schedule;
6. require final human rule review before any typed order intent.

No execution authority was added.
