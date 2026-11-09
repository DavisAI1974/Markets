"""Cross-day table for the actual-input passes: first-family four arms, dipole post-recognition, archived match."""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
TAGS = ("oct18", "oct17", "oct03", "oct02")


def share(h, a, b):
    return round(h[a] / max(1, h[a] + h[b]), 3)


def main():
    out = {}
    print("==== first-family four arms (actual family starts)")
    F = {t: json.load(open(HERE / f"first-family-four-arm-{t}-summary.json")) for t in TAGS}
    hdr = ["population", "eligible_recent_flow_defined", "pre_cursor_agreement", "reproduced_screen", "inverse_stack"]
    for k in hdr:
        print(f"  {k:30s}", [F[t].get(k) for t in TAGS])
    print("  full depth bid>ask share   ", [round(F[t]["full_depth_sign_counts"].get("1", 0) / F[t]["population"], 3) for t in TAGS])
    print("  full depth ratio median    ", [round(F[t]["full_depth_ratio"]["median"], 3) for t in TAGS])
    for arm in ("baseline", "baseline_plus_flow", "baseline_plus_book", "baseline_plus_both", "both_agree", "original_stack_sell_side", "inverse_stack_buy_side"):
        for h in ("5", "60", "300"):
            row = []
            for t in TAGS:
                a = F[t]["arms"].get(arm)
                if not a or h not in a["horizons"] or not a["horizons"][h].get("n"):
                    row.append(None); continue
                x = a["horizons"][h]
                row.append((x["n"], share(x, "continued", "reversed"), x["median_ticks"]))
            print(f"  {arm:26s} {h:>4s}s  n/continue-share/median:", row)
    print("  day reference, unoriented up share at 600 s:", [share(F[t]["day_reference"]["all_749"]["horizons"].get("600", F[t]["day_reference"]["all_749"]["horizons"].get("300")), "up", "down") for t in TAGS])
    print("\n==== dipole post-recognition (actual archived recognitions)")
    D = {t: json.load(open(HERE / f"dipole-post-recognition-{t}-summary.json")) for t in TAGS}
    print("  recognitions / finalization-only:", [(D[t]["recognitions"], D[t].get("finalization_only", [])) for t in TAGS])
    for arm in ("baseline", "flow/same_direction_at_emission", "flow/opposite_direction_at_emission", "book/aligned", "book/opposed", "polarity/buy_birth", "polarity/sell_birth"):
        for h in ("1", "5", "20", "60", "300"):
            row = []
            for t in TAGS:
                a = D[t]["arms"].get(arm)
                if not a or h not in a["horizons"] or not a["horizons"][h].get("n"):
                    row.append(None); continue
                x = a["horizons"][h]
                row.append((x["n"], share(x, "with_birth", "against_birth")))
            print(f"  {arm:38s} {h:>3s}s n/with-share:", row)
    for t in TAGS:
        c = D[t]["day_reference"]["touch_imbalance_control_all_active_seconds"]
        ti = c.get("touch_imbalance", {})
        print(f"  {t} control (all active seconds, touch imbalance): seconds {c.get('seconds')}", {h: (round(v.get('with_heavier_side', 0) / max(1, v.get('with_heavier_side', 0) + v.get('against_heavier_side', 0)), 3)) for h, v in ti.items()})
    print("\n==== archived recognition match inside the exhaustion pass")
    for t in TAGS:
        e = json.load(open(HERE / f"exhaustion-clock-{t}-summary.json"))
        dn = e["day_native"]
        print(f"  {t}: archived {e['archived_recognitions']} | detector events {dn['events']} | archived births matching a detector t0 {e['archived_birth_seconds_matching_day_events']} | archived recognition offset {dn.get('archived_recognition_offset_s')} | recognised after confirm {dn.get('archived_recognition_after_confirm')}")


if __name__ == "__main__":
    main()
