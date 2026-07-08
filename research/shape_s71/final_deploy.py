"""S77: FINAL deploy blend — shared $5k across all cells at the realistic PATIENT MAKER-EXIT $/hr
(exit_all.txt, from exit_model.py) capped at each cell's fill capacity (fillocc.txt). This is the honest
deploy number: patient maker-exit (92-99% maker fills) + rebate + x0.9 fill + shared-$5k greedy allocation.

    python3 final_deploy.py
"""
import re
CAP = 5000.0
MAJ = {"btc", "eth", "sol", "xrp", "doge"}

dph = {}
for ln in open("/tmp/kbook/exit_all.txt"):
    m = re.match(r"\s*([A-Z]+)\s+\d+\s+[\d.]+\s+[\-\d.]+\s+([\-\d.]+)", ln)
    if m:
        dph[m.group(1).lower()] = float(m.group(2))
cap = {}
for ln in open("/tmp/kbook/fillocc.txt"):
    m = re.match(r"\s*([A-Z]+)\s+[\d.]+\s+[\d,]+\s+[\d,]+\s+([\d,]+)\s+\d+", ln)
    if m:
        cap[m.group(1).lower()] = float(m.group(2).replace(",", ""))
for c in MAJ:
    cap.setdefault(c, CAP)

cells = sorted(((c, dph[c], cap.get(c, CAP)) for c in dph), key=lambda x: -x[1])
rem = CAP; bank = 0.0; sc = 0.0
print("=== FINAL DEPLOY BLEND (patient maker-exit, x0.9 fill, shared $5k) ===")
print(f"{'cell':>6}{'deployed$':>11}{'$/hr@5k':>9}{'earns':>8}")
for c, d, cp in cells:
    if rem <= 0 or d <= 0:
        break
    take = min(cp, rem); earn = take / CAP * d; bank += earn; rem -= take
    if c not in MAJ:
        sc += take
    print(f"{c.upper():>6}{take:>11,.0f}{d:>9.1f}{earn:>8.2f}")
print(f"\n  BANK $/hr on $5k = {bank:+.1f}  ({bank/CAP*100:+.2f}%/hr) | small caps ${sc:,.0f} of $5k ({sc/CAP*100:.0f}%)")
print("  CAVEATS: 4.7h recent window; mid-price P&L (no spread — flatters wide-spread cells XMR/TON);")
print("  576-config train selection; requires the Kraken maker-rebate tier. Confirm live before sizing.")
