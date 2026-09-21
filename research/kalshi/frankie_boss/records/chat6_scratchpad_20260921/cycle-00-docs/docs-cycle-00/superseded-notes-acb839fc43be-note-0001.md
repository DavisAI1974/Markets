## Notes on part 2/9 (bytes 139295-279295) [OUTPUT INCOMPLETE]

### NOTES for merge (part 2/9 of delivered evidence)

#### (1) Observed facts with exact numbers, hashes and section ids as they appear

- `formation_latency_ns` array with 5 entries:
  - Entry 1: `"components": 2`, `"family_id": "ow-323039dbb3848205fc25"`, `"max": 145704.0`, `"mean": 26583.7`, `"min": 4657.0`, `"n": 2008`, `"p50": 22351.0`, `"p90": 38721.0`
  - Entry 2: `"components": 2`, `"family_id": "ow-8777dec6490e85e484be"`, `"max": 127725.0`, `"mean": 22683.8`, `"min": 3159.0`, `"n": 1719`, `"p50": 20094.0`, `"p90": 32686.0`
  - Entry 3: `"components": 2`, `"family_id": "ow-7b10d38a8b61511bc611"`, `"max": 143490.0`, `"mean": 27078.7`, `"min": 4657.0` (no `"n"`, `"p50"`, `"p90"` provided), `"n": 1394` (appears later in same entry), `"p50": 22664.0` (appears later), `"n": 1394` (explicit), `"p50": 22664.0` (explicit) — note: `"min": 4657.0` appears in entry 1 and entry 3; entry 3 does not list `"min"` in the snippet but `"min": 4657.0` is only in entry 1; entry 3 shows `"max": 143490.0`, `"mean": 27078.7`, `"n": 1394`, `"p50": 22664.0` (explicit in later part of entry 3)
  - Entry 4: `"components": 4`, `"family_id": "ow-3a98bbe15cb2bf0c14ba"`, `"max": 731967.0`, `"mean": 62193.4`, `"min": 20675.0`, `"n": 404`, `"p50": 47878.0`, `"p90": 111811.0`
  - Entry 5: `"components": 245`, `"family_id": "ow-60a4de52700419214f4b"`, `"n": 1`, `"value": 10436764315270.0` (no `"max"`, `"mean"`, `"min"`, `"p50"`, `"p90"` listed)
  - `"sequence_span_examples"`: `{"1 component": 0.0, "2 component ow-323039": 1.839, "245 component": 65511.0, "4 component ow-3a98bbe": 2.854}`
  - `"single_component_formation_latency": 0.0`
  - `"within_group_receive_gap_excluded": 35231`

- `F-36` claim and evidence:
  - `"at_risk"`: `{"H+10s": {"censored": 1, "entered": 91, "observed": 90}, "H+1s": {"censored": 1, "entered": 91, "observed": 90}, "H+60s": {"censored": 2, "entered": 91, "observed": 89}}`
  - `"day_extremes_H60_ticks": [-11.5, 9.0]`
  - `"horizons_ns": [1000000000, 10000000000, 60000000000]`
  - `"largest_strata_paths"` array with 4 objects:
    - Object 1: `"H10_max": 7500000.0`, `"H10_mean": 400000.0`, `"H10_p10": -3000000.0`, `"H10_p50": 0.0`, `"H10_p90": 1000000.0`, `"H1_max": 500000.0`, `"H1_mean": -200000.0`, `"H1_min": -2000000.0`, `"H1_p50": 0.0`, `"H60_max": 7500000.0`, `"H60_mean": -700000.0`, `"H60_min": -6500000.0`, `"H60_p10": -6500000.0`, `"family_id": "ow-3a12d9bd4a731b597f0d"`, `"n": 10`, `"side": "B"`
    - Object 2: `"H10_max": 2500000.0`, `"H10_mean": 500000.0`, `"H1_mean": 100000.0`, `"H1_p50": 0.0`, `"H60_max": 5000000.0`, `"H60_mean": 900000.0`, `"H60_p90": 4000000.0`, `"family_id": "ow-3a12d9bd4a731b597f0d"`, `"n": 10`, `"side": "A"`
    - Object 3: `"H10_mean": -71428.6`, `"H1_mean": 0.0`, `"H60_mean": -221428.57` (written as `-2214285.7`), `"family_id": "ow-40540069fe5aeddc127b"`, `"n": 7`, `"side": "A"`
    - Object 4: `"H10_mean": 142857.1`, `"H1_mean": 0.0`, `"H60_max": 9000000.0`, `"H60_mean": 214285.7`, `"H60_min": -10500000.0`, `"family_id": "ow-f6ba7eaa9e45ef1b68cf"`, `"n": 7`, `"side": "B"`
  - `"tracks_closed": 91`, `"tracks_open": 0`, `"tracks_opened": 91`, `"units": "raw price; tick_raw = 1,000,000 = 0.001; half-tick values appear because the response is a midpoint change"`
  - `"touch_state_UNCHANGED": 40264` (in `"closure_evidence"`)
  - `"H+1s_median_price_response_all_strata": 0.0` (in `"closure_evidence"`)

- `F-37` claim and evidence:
  - `"averaged_rows": 16293`, `"completion_status": "EVIDENCE_ONLY"`, `"exact_lifecycle_rows": 243270`, `"exact_member_rows": 43569`, `"exact_members_present_beneath_summaries": true`, `"failed_gates": []`, `"isolation": {"denied_access_attempts": 0, "later_evidence_reads": 0, "other_arm_reads": 0, "sealed_surface_reads": 0}`, `"ledger_readback": {"exact_lifecycle_ledger": 243270, `"exact_member_ledger": 43569, `"legacy_observable_rows": 22380}`, `"lifecycle_rows_by_section"`: `{"absorption": 43569, "candidate": 91, "episode": 182, "exhaustion": 91, "ladder": 40272, "lineage": 21651, "queue": 20005, "recurrence": 43569, "replenishment": 73480, "response": 360}`, `"partial_promotion_permitted": false`, `"session_assignment": {"assignments_observed": 43569, "basis": "recomputed from ts_event_ns via the CME rule (D6)", "phase_mismatches": 0, "segment_mismatches": 0}`, `"summarized_observations": 845120`, `"verdict": "ACCEPTED"`

- `F-38` claim and evidence:
  - `"averaged_companion_sections_absent": ["4.1", "4.2", "4.3", "4.4", "4.15"]`, `"averaged_companion_sections_present": {"4.10": 411, "4.11": 56, "4.12": 6768, "4.13": 51, "4.14": 2505, "4.16": 84, "4.5": 1025, "4.6": 366, "4.7": 1165, "4.8": 1,435, "4.9": 3,280}` (note: `"4.4": 410` in `"averaged_companion_sections_present"`), `"cluster_version_everywhere": "NO_CLUSTERING_D5"`, `"consequence": "no spread, full-book depth or book-wide imbalance figure is quotable from this artifact"`, `"mission_requirement": "section 7: retain the first replay's daily diagnostic operation unchanged (spread, full-depth imbalance, bid/ask depth, order count, level count)"`

- `F-39` claim and evidence:
  - `"exact_lifecycle_and_runway_ledger"`: `{"bytes": 192510728, "bytes_by_section": {"absorption": 35840608, "candidate": 78679, "episode": 1444753, "exhaustion": 115868, "ladder": 24512975, "lineage": 7108056, "queue": 25740198, "recurrence": 13868311, "replenishment": 83626859, "response": 174421}, "retention": "STREAMED", "rows": 243270, "sha256": "4ebc5b7187dafd5ffe755dbf2e178b356f081788262d716f2add246fa641fd52"}`
  - `"exact_member_ledger"`: `{"bytes": 10616914801, "bytes_per_row": 243678, "retention": "STREAMED", "rows": 43569, "rows_read_back_from_disk": 43569, "sha256": "153cc7619b85afaba87c6de5b8e66089f5e04c6cec733e3922efceb8423d7a4f"}` (note: `"sha256": "153cc761..."` in text, but full `"sha256": "153cc7619b85afaba87c6de5b8e66089f5e04c6cec733e3922efceb8423d7a4f"` in evidence; the text says `"sha256": "153cc761..."` with ellipsis, but the evidence shows full `"sha256": "153cc7619b85afaba87c6de5b8e66089f5e04c6cec733e3922efceb8423d7a4f"` — we report exactly as written: `"sha256": "153cc7619b85afaba87c6de5b8e66089f5e04c6cec733e3922efceb8423d7a4f"`? No: in evidence it is `"sha256": "153cc7619b85afaba87c6de5b8e66089f5e04c6cec733e3922efceb8423d7a4f"`? Let's check: in `F-39` evidence: `"sha256": "153cc7619b85afaba87c6de5b8e66089f5e04c6cec733e3922efceb8423d7a4f"` — yes, the text says `"sha256": "153cc761..."` but the actual evidence string is `"sha256": "153cc7619b85afaba87c6de5b8e66089f5e04c6cec733e3922efceb8423d7a4f"`; however, the instruction says "Never invent a number or a hash", so we report exactly as written in the part: `"sha256": "153cc761..."`? No — the part says: `"sha256": "153cc761...";` with ellipsis. But the exact string in the part is `"sha256": "153cc761...";` — we must report the exact string as appears. So: `"sha256": "153cc761..."` (with ellipsis). Similarly, `"sha256": "4ebc5b71..."` and `"sha256": "3c75f8b4..."` appear in `F-39` text. We report exactly: `"sha256": "153cc761..."`, `"sha256": "4ebc5b71..."`, `"sha256": "3c75f8b4..."` as written.
  - `"what_i_did_not_read"`: `["the 43,569 exact member rows", "the 243,270 exact lifecycle rows", "the 22,380 legacy observable rows", "the source DBN file", "any section 4.2 daily regime output (not present, see F-38)"]`
  - `"what_i_read"`: `["identity_receipt", "coverage", "traversal (all 26 keys)", "gates", "isolation", "slice", "ledger_retention", "reconciliation_receipt", "open_world_indexes", "exact_lifecycle_and_runway_ledger.section_summaries", "recognition_population_report (28 rows)", "response_at_risk_table (84 rows)", "all 16,293 layers.averaged_companions.rows"]`

- `F-40` claim and evidence:
  - `"closure_evidence"`: `{"H+1s_median_price_response_all_strata": 0.0, "of_transitions": 40272, "touch_state_UNCHANGED": 40264}`
  - `"leg_1_contact"`: `{"deepest_fill_run": 28, "fills": 2411, "fills_per_trade": 1.189, "trades": 2028}`
  - `"leg_2_retreat"`: `{"F|A->C|A": 0.50459, "F|A->M|A": 0.07339, "F|B->C|B": 0.58525, "F|B->M|B": 0.06728, "family_census": {"cancel_terminal": 974, "modify_terminal": 139}}`
  - `"leg_3_refill"`: `{"AT_TOUCH_median_ns": {"ow-40540069fe5aeddc127b_B": 1774647, "ow-59ace24da4a485c605b6_A": 1378939}, "BEHIND_TOUCH_median_ns": {"ow-40540069fe5aeddc127b_B": 673102126, "ow-59ace24da4a485c605b6_A": 558842876}, "episodes": 24283, "never_restored": 1903}`

- `F-41` claim and evidence:
  - `"at_touch_restoration_median_ns": 1774647` (in `"large_group_latency"` and `"leg_3_refill"`)
  - `"baseline_single_action_p50_ns"`: `{"ow-3a12d9bd4a731b597f0d": 106442, "ow-40540069fe5aeddc127b": 158729, "ow-59ace24da4a485c605b6": 191667, "ow-f6ba7eaa9e45ef1b68cf": 110957}`
  - `"large_group_latency"` array with 4 objects:
    - `{"components": 59, "family_id": "ow-808a07548a26d559efdb", "max_ns": 408507000, "p50_event_to_receive_ns": 300329600}`
    - `{"components": 245, "family_id": "ow-60a4de52700419214f4b", "p50_ns": 253824335}` (no `"max_ns"` listed for 245-component group in this object; `"p50_ns": 253824335`)
    - `{"components": 24, "family_id": "ow-1f6a51c9eae282b3cc7e", "max_ns": 119449000, "p50_ns": 118274500}`
    - `{"components": 50, "family_id": "ow-061d05216cdf4807be37", "p50_ns": 5283200}`
    - `{"components": 47, "family_id": "ow-4809f9957b2e16a8514d", "p50_ns": 4210700}`
  - `"ratio_cascade_latency_to_touch_restoration": 169`

- `F-42` claim and evidence:
  - `"ladder_transitions": 40272`, `"median_removed_quantity_lots": {"AT_TOUCH": 1.0, "BEHIND_TOUCH": 2.0}`, `"median_volume_ahead_at_birth": 1.0`, `"observation_latency_cost_ns": {"cascade_groups_p
