"""_canary_quiet_gate.py — prove the QuietFloor gate is wired into the live dipole correctly (S43 #4).

Three load-bearing checks on a REAL cell (btc_kraken realbins):
  1. BIT-FAITHFUL: the causal one-tick `IncrementalQuietGate` reproduces the batch `QuietFloor.gate()`
     exactly (the hot-path port must equal the offline math).
  2. LEAKAGE-SAFE: the QuietFloor is fit on the TRAINING quiet cells only; the gate at t reads imb[t-1]
     (no look-ahead). We verify gating the TEST slice never touches the future.
  3. CHURN CUT, DIRECTION KEPT: the gated dipole fires far less often than the raw-level dipole
     (stops churning through trends), and where it DOES fire its direction equals sign(level).

Run: python _canary_quiet_gate.py
"""
import numpy as np

from odcore.quiet_floor import fit as fit_quiet
from odcore.incremental import IncrementalQuietGate
from odcore.io import load_bins
from odcore.generators import dipole_gated, ofi_signal

K = 1.5
TRAIN_FRAC = 0.6


def main():
    s = load_bins("realbins/btc_kraken_bins.json")
    tot = s.buy + s.sell
    imb = np.where(tot > 0, (s.buy - s.sell) / (tot + 1e-12), 0.0)
    quiet = tot <= 0.0
    n = len(imb)
    print(f"cell=btc_kraken  n={n}  quiet_cells={int(quiet.sum())} ({100*quiet.mean():.1f}%)")

    # Fit on training quiet cells only (no look-ahead).
    floor = fit_quiet(imb, quiet, train_frac=TRAIN_FRAC)
    print(f"QuietFloor: phi={floor.phi:.4f} c={floor.c:+.4f} sigma={floor.sigma:.4f} "
          f"r2_quiet={floor.r2_quiet:.3f} n_quiet_train={floor.n_quiet}")

    # --- Check 1: incremental (causal, one tick at a time) == batch gate, bit-faithful ---
    batch_gate = floor.gate(imb, k=K)                 # vectorized
    inc = IncrementalQuietGate.from_floor(floor, k=K)
    inc_gate = np.array([inc.update(float(x)) for x in imb], dtype=bool)
    mism = int((batch_gate != inc_gate).sum())
    print(f"[1] incremental vs batch gate mismatches = {mism}/{n}")
    assert mism == 0, "incremental gate diverges from the batch QuietFloor.gate()!"

    # also the deploy form (signal, advancing state) matches sign(level) where the gate is open
    inc2 = IncrementalQuietGate.from_floor(floor, k=K)
    inc_sig = np.array([inc2.gated_signal(float(x)) for x in imb])
    batch_sig = floor.gated_signal(imb, k=K)
    assert int((inc_sig != batch_sig).sum()) == 0, "incremental gated_signal != batch gated_signal!"
    print("    incremental gated_signal == batch gated_signal (sign(level) where open, else 0)")

    # --- Check 2: leakage — gating the TEST slice uses only the (frozen) fit + the past ---
    cut = int(n * TRAIN_FRAC)
    # Re-deriving the gate on the test slice alone (seeded with the last train imb) reproduces the
    # full-series gate on the test region → the gate at t never reads t+1.
    inc3 = IncrementalQuietGate.from_floor(floor, k=K)
    for x in imb[:cut]:
        inc3.update(float(x))                          # warm the prev-imb state through train
    test_gate_causal = np.array([inc3.update(float(x)) for x in imb[cut:]], dtype=bool)
    assert int((test_gate_causal != batch_gate[cut:]).sum()) == 0, "test-slice gate is not causal!"
    print(f"[2] leakage-safe: test-slice causal gate == full-series gate on [{cut}:{n}] (no look-ahead)")

    # --- Check 3: churn cut, direction preserved ---
    raw = ofi_signal(s, thresh=0.0)                    # the raw-level dipole (fires on every leaning bin)
    gated = dipole_gated(s, train_frac=TRAIN_FRAC, k=K)
    raw_fire = float((raw != 0).mean())
    gated_fire = float((gated != 0).mean())
    open_mask = gated != 0
    # where gated fires, its sign must equal the raw level's sign
    sign_match = bool(np.all(np.sign(gated[open_mask]) == np.sign(imb[open_mask])))
    print(f"[3] raw-level dipole fires {100*raw_fire:.1f}% of bars; gated dipole fires "
          f"{100*gated_fire:.1f}% (churn cut {100*(1-gated_fire/max(raw_fire,1e-9)):.0f}%)")
    print(f"    direction preserved where gated fires: {sign_match}")
    assert gated_fire < raw_fire, "gate did not reduce firing — it should stand aside through trends!"
    assert sign_match, "gated direction must equal sign(level)!"

    print("\nCANARY PASS — QuietFloor gate is bit-faithful, leakage-safe, and cuts churn "
          "while keeping the level's direction.")


if __name__ == "__main__":
    main()
