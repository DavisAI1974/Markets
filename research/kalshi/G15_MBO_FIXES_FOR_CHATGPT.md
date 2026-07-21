# G15 MBO refine - little things to fix ahead of time (running handoff for ChatGPT, S103)

Captured live while running the G15 MBO+L1 refine brief on branch `chatgpt/ng-forecaster-s103-audit`.
These are small integration snags + one real data-spec issue. Fixing them in the engine/brief/collector
ahead of the next group (G16/G17) saves the same debugging. (Running list - appended as the full group
completes.)

## DATA SPEC (the important one)
1. **Kalshi-underlying basis vs NG.n.0 continuation.** The historical `nymex/ng_mbo/` + `nymex/ng_l1/`
   year pulls use **NG.n.0 (open-interest continuation)**. By mid-March that is already **NGK26/May
   (instrument 996)**, so for G15's pre-roll days (0313-0319) the continuation is the WRONG leg - the
   brief's contract map + anchor need **NGJ26/April (~3.132)**. The pilot anchor came out **3.122 (May)**.
   FIX GOING FORWARD: for a group that straddles a Kalshi-underlying roll, pull the SPECIFIC contract legs
   (raw_symbol NGJ26 pre-roll, NGK26 post-roll) - not NG.n.0 - or add a leg-map the driver honors. The
   0320-0327 post-roll days (NGK26) happen to match NG.n.0 and are fine.
2. **Definition date not in the MBO stream.** `build_feature_state` requires
   `instrument_identity.definition_date` (non-null) or it stands down ("instrument identity missing:
   definition_date"). A pure MBO `.dbn.zst` (schema=mbo) carries no definition records, so the driver has
   to supply it. FIX: include the `definition` schema in the archive (the live collector already requests
   it), or expose a definitions sidecar so replay can populate identity without a stand-down.

## ENGINE / DBN INTEGRATION SNAGS (small, mechanical)
3. **DBN record type name is `MBOMsg` (all caps)** in databento 0.81, not `MboMsg`. A `type(r).__name__
   == "MboMsg"` filter silently drops every record.
4. **`action`/`side` are enums** (`Action.TRADE` with `.value == 'T'`, `Side.BID`='B', etc.), not chars.
   Pass them raw to `NGLiveOperator.on_mbo/on_trade` (it normalizes via `_action/_enum`); detect trades
   with `getattr(action,'value',action) == 'T'`. Prices are int 1e-9 fixed-point (`price/1e9`); undefined
   = `9223372036854775807` -> None.
5. **`source_mode` must be `"historical_replay"`** (SOURCE_MODES = {"historical_replay","live"}). The
   intuitive `"historical"` raises FeatureStateError. Worth documenting in the brief's replay step.
6. **`odcore` import path.** `ng_live_operator.py` imports `from odcore.info_dipole import ...` (repo
   root). Running from `research/kalshi` needs `PYTHONPATH=<repo root>`. A sys.path shim in the operator
   (like the test's KALSHI_DIR insert) would remove the footgun.

## BOX / OPS SNAGS (for any box-side pull the brief triggers)
7. **The box instance role `Ssm` cannot write S3** (AccessDenied on PutObject). Historical pulls must run
   with the tx-pair AWS keys IN THE PROCESS ENV (env vars override the role in boto3's chain). The L1/MBO
   pulls work only because they export the keys before launch.
8. **SSM default shell is dash**, not bash - no `${VAR:0:n}` / `${#VAR}` inline. Use a bash launcher file.
9. **Live MBO/MBP-10 are NOT authorized** on the $179 Standard plan ("Not authorized for mbo schema");
   they need the ~$1,500/mo Plus tier. The live collector leads with an `mbo` subscribe and hot-loops on
   ErrorMsg until that entitlement exists - so the live path is historical-only until the tier is bought.

## WHAT WORKED (no change needed)
- The causal engine itself: `NGLiveOperator` + `build_feature_state` replay real MBO cleanly and produce
  correct feature states WITH proper data-quality stand-downs (thin Sunday -> flow stands down, queue
  stays). Historical/live parity via the shared operator holds. No second-engine / S92-predictor issue.
