## Note (Session 23 update — 2026-06-08) — MARKETS: dipole trade runner built; data scaled to a current month + git unstuck

S23 built the runner that earns the chem-dipole validation and fixed the data pipeline it runs on.

**Built (`scripts/od_trade_dipole_run.py`, commits `26be859`/`b97d377`):** replays the
adaptive_backtester generators (ALL generators incl. the dipole one — Greg's Option-2 call) on
minute bars to get labeled win/lose trades; slices each trade's pre-entry orderflow window from
the 1s BinSeries; builds the 15-dim c_i (`dipole_trade.trade_coupling_vector`); runs the
in-sample positive control + embargoed walk-forward gate (`odcore/validation.py`), printing
three standardization modes (none/scale/pool). It is **resumable** — each source checkpoints to
`realbins/_dipole_cache/`, so a killed run resumes; `--eval-only` gives an instant readout.

**Data unblock:** the git `data/btc-bins`/`data/eth-bins` branches had stalled at 2026-05-17
(~10 days). The collectors kept writing locally to `E:\Markets\live_data_history\<date>\<src>_bins.jsonl`
(~2026-02-23 -> today, 5 assets x 3 venues). `scripts/build_realbins.py` merges that daily JSONL
into the merged `realbins/<src>_bins.json` both loaders consume unchanged; rebuilt 30 days x 15
sources. Pushed **gzipped** 30-day bins back to git (`aa4736d`/`977f979`; under GitHub's 100-MiB
cap) and `session_start.sh` now gunzips — so future hooks materialize current data.

**Unresolved finding (S24 to confirm at scale):** on a small/imbalanced smoke sample the
in-sample dipole did NOT reproduce the reference convex `c=1.309, R^2=0.943` — the quadratic
collapses to `c~=0` in all three modes (pool-mode mean-centering forces antiparallel centroids
=> `H_a==-H_b`, a tautology and a **latent issue in the ported core**; none/scale stay linear).
Likely cause: the 15-dim c_i is too thin/collinear. STRONG LEAD: the local folder
`_full_pipeline_winners_preentry_cs100_v2` (2026-05-28) may already hold a richer ~100-dim
labeled trade set.

**Honest status:** no net-of-cost edge demonstrated; the gate (`odcore/validation.py`) is
unchanged and unmet. The full 15-source validation numbers are still pending (run is long +
resumable; relaunched at session end) — that is S24's first action. Hygiene fixed so S24 starts
fast: `safe.directory '*'` is global (no more "dubious ownership"); onboarding docs live IN GIT
(never re-upload/paste); the data branches are current. See `SESSION_HANDOFF_2026-06-08_S23.md`
+ `KICKOFF_2026-06-08_S24.md`; memory `markets-data-lives-local-not-git`.

