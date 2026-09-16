# SESSION HANDOFF - S103 (work date 2026-07-21) - G15 refine merged, CANONICAL agent files built, G16 blind PANEL run+refined+merged (brain s102.1 -> s102.3), the recurring-flaw memo written for ChatGPT

Branch: `claude/ng-coach-agent-loop-5ha5bf`. git = CODE, S3 = DATA. Model tiering: Fable orchestrates +
adjudicates + merges; Opus workers run blind/refine; ChatGPT/people do off-repo docs.

## SESSION TOTAL (chronological)

1. **ENV**: creds (tx-pair, ...4170). **The InvalidAccessKeyId fix CONFIRMED**: the container's
   placeholder AWS env vars override the file via boto3 setdefault -> run platform_sync/boto3 with
   `env -u AWS_ACCESS_KEY_ID -u AWS_SECRET_ACCESS_KEY`. Shared full-history stores pulled ONCE.

2. **G15 REFINE (S103 opener) -> MERGED s102.2 (34 plays)**: blind 8/12 drift -3260 -> refined 10/12,
   cum guess -650 vs actual -600, every day <=160. FINDING: "magnitude grossly too deep" REFUTED - the
   down-days were well-calibrated; the -3490 was TURN-DETECTION (0318 the engine: a missed give-back-
   exhaustion turn UP whose wrong level propagated; 0327 expiry-covering rally; 0326 over-sized counter).
   Rules: giveback_exhaustion_boundary flow-absorption arm (0.70->0.72), NEW shoulder_counter_print_
   damping (0.4), weekend_crest_friday 0327 expiry-covering split (0.50->0.55). 28 incumbents
   byte-identical. Renders printed (g15_refined.png, g15_refined_overlay.png). run_g15_rt_s102.py
   parametrized backward-compatibly.

3. **CANONICAL DROP-IN AGENT FILES (Greg-ORDERED)**: the G16 blind prompts + the refine prompt are now
   STATIC reusable files in `research/kalshi/agents/`: blind_shared.md + blind_angle_{storage,
   positioning,weather}.md (the 3-agent panel) + refine.md + README.md (turnkey per-group loop). Drop
   the SAME files into every group; ONLY the brain (via refine) + group data change. NO per-group prompt
   re-authoring / selftest / store re-pull. RENDERS = continuous_rt.py (change dates), NOT per-group
   scripts. This was Greg's wasted-cycles fix.

4. **MULTI-GROUP PRECHECK (Greg-ordered "few groups precheck at the beginning")**: GROUP_PRECHECK_S103.md
   records the shared substrate (once) + the roll map verified from NG_structure.json (May LTD 04-28 ->
   roll 04-21; June LTD 05-27 -> roll 05-20) + windows: G16 May clean, G17 two-leg May->June seam ~0421,
   G18 clean June.

5. **G16 BLIND PANEL (Sun 03-29 - Fri 04-10, 11 sessions; Good Friday 04-03 dark = extended weekend;
   EIA 04-02 & 04-09; clean May/996; anchor 03-27 close 3.035 up)** - the FIRST 3-agent panel (Greg's
   idea to attack weekends). Agents A (storage/S3-first), B (positioning-first), C (weather-continuation-
   first), each blind-walled. Synthesized per-event into grp16.json. **BLIND 8/11 direction, cum guess
   -1455 vs actual -3820 (drift +2365) - UNDER-sized a steady S3 injection-bearish bleed 3.035->2.653.**
   Panel value CONFIRMED: consensus nailed the down direction + down days + the 04-05 extended-weekend
   reopen (+400); the 3 misses (04-01, 04-06, 04-07) were EXACTLY the flagged divergence days.

6. **G16 REFINE -> MERGED s102.3 (36 plays)**: refined **11/11 direction, drift +40, every day <40**
   (Greg's "honest under 100" bar). Two findings:
   - **SELECTOR FLAW (Greg's "there's a flaw in our logic")**: the synthesis AVERAGED bimodal splits
     (04-07: A+250/B+500/C-300 -> flat, actual -220). NEW `selector.divergence_resolution`: on a
     storage-DOWN vs cold-add-UP split in an S1-void injection regime, default DOWN; the cold-add wins
     ONLY if near-window HDD >= ~16.4 AND D-1 session_b_share >= 0.50 (both pre-existing thresholds, no
     new constant). n=3 (04-01/04-06/04-07 all resolve down) + positive control 04-05.
   - **MAGNITUDE (the recurring ping-pong)**: the +2365 under-drift = down-day UN-damping - the blind
     mis-applied G15's "don't over-size the shoulder" as a UNIFORM damp, but that lesson is scoped to
     COUNTER prints only. NEW `magnitude.s1void_injection_chain_bleed` (chain-sided down days in a live
     sell-tape deliver full trend/coil bands). Load-bearing find: tape_conditions.session_b_share was
     sub-0.50 on ALL 11 D-1 sessions = a persistent sell-tape = 11/11 direction if followed.
   - 31 incumbents byte-identical; 3 additive g16_forward_evidence notes. Renders printed
     (g16_continuous.png blind, g16_refined_continuous.png refined). Backups s102.{2}_backup.json.

7. **THE PROBLEM MEMO (Greg -> ChatGPT)**: `research/kalshi/NG_FORECASTER_PROBLEM_MEMO_S103.md` - a
   verbose, self-contained diagnosis of the RECURRING flaw for an outside reader: the structural
   blind(30-70%)-vs-refine(90-100%) gap; the magnitude error FLIPPING SIGN block-to-block from
   mis-scoped lessons; the selector averaging bimodal splits; the under-weighted order-flow direction
   nowcast. 4 candidate root causes + 5 questions. Greg is handing it to ChatGPT for insight to fold in
   before G17.

## IN FLIGHT AT CLOSE
- BOX L1 pull UNTETHERED (~105/250 days at S103 open, up to ~2025-11-20, $0.00 in-sub, alive). Check
  nymex/ng_l1/_DONE; queue CL L1 when done; stop box only when NG-L1+CL-L1+pull_rest all done (pull_rest
  DONE). ChatGPT may be collecting live MBO on the box + pulling data to S3 - coexist, do not collide.

## OPEN / CARRIED (for S104)
- **G17 (04-12 - 04-24) is S104's opener** - TURNKEY via the canonical loop (two-leg May->June seam
  ~0421). Then G18 (clean June). FORWARD-TEST selector.divergence_resolution + s1void_injection_chain_
  bleed; incorporate any ChatGPT insight on the problem memo.
- pyth: NOT a concern (daily-settle number only, Greg S103).
- Voxa / two-coach nod / repo-private: still pending Greg (unchanged from S102).

## RULES (unchanged - see KICKOFF_2026-07-22_S104.md guards block)
