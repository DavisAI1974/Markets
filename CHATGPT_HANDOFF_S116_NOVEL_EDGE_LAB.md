# ChatGPT Handoff — S116 Novel Edge Lab

**Branch:** `chatgpt/novel-edge-lab-s116`  
**Draft PR:** #7 — Add read-only Novel Edge Lab candidate panel  
**Base:** `claude/kalshi-agents-coordinator-guard-sg0n15`  
**Date:** 2026-08-06

## What Greg asked for

Create separate boxes for the newly researched hidden-edge candidates on the trading
platform and wire in everything that is causally and operationally safe now.

Greg also asked whether buy and sell sides should be balanced. The answer built into the
panel is: **balance the intended risk, not gross dollars, displayed size, or order count.**

## What is built

### New dashboard view

A new **Novel Edge Lab** is injected into the existing S100 Mission Control shell.

- New rail item: `Novel`
- New command-palette item: `Novel Edge Lab`
- One separate card per candidate
- No changes to the large baseline `dashboard/frontend/index.html`
- Existing visual language, navigation and read-plane doctrine preserved

### Candidate cards

The panel currently contains 10 preregistered candidates:

1. Same outcome, different Kalshi wrapper
2. CME option-implied digital versus Kalshi binary
3. Monthly-expiry underlying-month fork
4. Settlement-clock and source residual
5. Cross-commodity oracle-health factor
6. EIA-930 revision-vintage gas-burn residual
7. Renewable covariance collapse versus hydro headroom
8. STEO balance-component revision topology
9. Kalshi weather posterior as a gas-acceptance clock
10. Freeze-driven NG versus crude bifurcation

Every card displays:

- rank;
- mechanism family;
- structural/predictive verdict;
- potential value, causal defensibility, data readiness and testability;
- instruments;
- causal clock;
- balance mode;
- authority;
- immediate-watch status;
- use conditions;
- kill test;
- required local paths;
- existing supporting code/docs;
- explicit non-executable provenance.

### Dynamic readiness

`dashboard/adapters/novel.py` checks the real local repo paths at request time.

Readiness states:

- `WIRED_INPUTS`
- `PARTIAL_INPUTS`
- `AWAITING_DATA`

These states mean local input availability only. They do not mean the candidate is a
validated edge.

### Dynamic 48-hour watch schedule

The API generates ET watch windows from the current clock:

- Thursday EIA storage → same-day NG options → Kalshi probability response
- Thursday post-release final NG probability/source check
- daily WTI source/expiry approach
- daily 5:00 p.m. commodity determination approach
- Friday daily-versus-weekly wrapper rule-hash check
- Friday cross-commodity provider-freshness check

All are `WATCH_ONLY` or `SHADOW`. Active market rules and executable books must still be
verified before interpreting a window.

### Balance modes

- `PAYOFF_NEUTRAL`: exact terminal-payoff match; suitable only for rule-identical claims
- `DELTA_NEUTRAL`: remove first-order underlying exposure; retain clock/source/vol basis
- `INVENTORY_SKEWED`: quote both sides but skew to reduce inventory
- `DIRECTIONAL`: bounded one-sided thesis; do not add a weak opposite leg for symmetry
- `WATCH_ONLY`: observe and record; no order route

## Files added or changed

- `dashboard/novel_candidates.json`
- `dashboard/adapters/novel.py`
- `dashboard/frontend/novel.js`
- `dashboard/frontend/novel.css`
- `dashboard/server.py`
- `dashboard/README.md`
- `.github/workflows/novel_edge_lab_ci.yml`
- `CHATGPT_HANDOFF_S116_NOVEL_EDGE_LAB.md`

## API

`GET /api/v1/novel/candidates`

The response includes:

- doctrine;
- balance-mode definitions;
- candidate registry;
- local-input readiness;
- dynamic 48-hour watch windows;
- summary counts;
- source files.

Hard invariant:

```text
execution_enabled = false
candidate authority ∈ {WATCH_ONLY, SHADOW}
```

## Validation

The Novel Edge Lab CI checks:

- Python compilation;
- registry JSON validity;
- JavaScript syntax;
- fixed Thursday 2026-08-06 10:13 ET schedule behavior;
- API endpoint registration;
- exactly 10 candidate cards;
- no candidate has execution authority.

The first CI run passed. A new run is triggered after each PR synchronization.

## What is wired now versus not wired

### Wired now

- UI navigation and separate cards
- real local-path readiness
- causal clocks and use windows
- 48-hour calendar watch schedule
- balance doctrine
- authority and truth-state labeling
- source and supporting-code references
- filters by immediate, structural, wired and awaiting

### Not yet wired

1. **Exact Kalshi rule canonicalizer**
   - fetch all active markets and complete rules;
   - normalize source, symbol, field, minute, inequality, rounding, fallback and early close;
   - hash the canonical object;
   - compare executable YES/NO books synchronously.

2. **CME digital builder**
   - form narrow vertical-implied digitals;
   - normalize multiplier, strike width and expiry;
   - map exact underlying month;
   - compare to Kalshi executable probabilities after costs.

3. **Contract identity resolver**
   - calendar-front, volume-front, OI-front, weekly-option underlying, Kalshi rule symbol;
   - next collision/roll date;
   - front-next spread needed to isolate month mismatch.

4. **EIA-930 vintage archive**
   - first and revised submissions stored separately;
   - availability timestamps;
   - imputation/revision flags;
   - no overwritten latest-only snapshots.

5. **Renewables/hydro interaction state**
   - point-in-time wind and solar forecast errors;
   - hydro headroom or response state;
   - BA breadth;
   - gas-marginality state.

6. **Five-step agnostic coupler runner**
   - causal/session preregistration first;
   - operator matrix;
   - structured-coupling test;
   - algebraic dipole;
   - lead/lag;
   - session-preserving tautology null;
   - untouched-forward exploitability after actual costs.

## Run locally

```bash
pip install fastapi uvicorn
python -m uvicorn dashboard.server:app --host 127.0.0.1 --port 8100
```

Open `http://127.0.0.1:8100/` and select `Novel`.

## Merge posture

Keep the PR draft until Claude confirms the injection approach is compatible with any
uncommitted dashboard work on the AWS box. The branch is based directly on Claude's current
coordinator branch and does not modify the baseline HTML.
