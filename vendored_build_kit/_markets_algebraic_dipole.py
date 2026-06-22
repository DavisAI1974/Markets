"""Markets-side algebraic dipole test (INFO-008 analog).

For each win/lose pair we already have full operator_coefficients (128-dim)
per trade. Define per-trade scalars:

  H_a_i = <c_i, c_win_centroid> / ||c_win_centroid||    # alignment with winners
  H_b_i = <c_i, c_lose_centroid> / ||c_lose_centroid||  # alignment with losers

Then test the universal algebraic dipole form:

  H_a^2 = alpha + beta * (H_a * H_b) + gamma * (H_a * H_b)^2

per pair AND pooled across all 12 pairs. Report R^2 for linear (beta only)
and quadratic (full) variants. R^2 > 0.6 = markets-side INFO-008.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

DISC = Path(r"E:\refrag\discoveries\operator_discoveries")
PAIRS = [
    "markets_btc_bybit_buy", "markets_btc_bybit_sell",
    "markets_btc_coinbase_buy", "markets_btc_coinbase_sell",
    "markets_btc_kraken_buy", "markets_btc_kraken_sell",
    "markets_eth_bybit_buy", "markets_eth_bybit_sell",
    "markets_eth_coinbase_buy", "markets_eth_coinbase_sell",
    "markets_eth_kraken_buy", "markets_eth_kraken_sell",
]

DOMAIN_SUFFIX = ""  # set by --domain-suffix CLI arg
WIN_SUFFIX: str | None = None
LOSE_SUFFIX: str | None = None

def _suffix() -> str:
    return f"_{DOMAIN_SUFFIX}" if DOMAIN_SUFFIX else ""

def _win_suffix() -> str:
    s = WIN_SUFFIX if WIN_SUFFIX is not None else DOMAIN_SUFFIX
    return f"_{s}" if s else ""

def _lose_suffix() -> str:
    s = LOSE_SUFFIX if LOSE_SUFFIX is not None else DOMAIN_SUFFIX
    return f"_{s}" if s else ""

def load_coefs(domain: str) -> list[list[float]]:
    d = DISC / domain
    if not d.is_dir():
        return []
    out: list[list[float]] = []
    for p in d.glob("*.json"):
        try:
            obj = json.loads(p.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        coefs = obj.get("result", {}).get("operator_coefficients")
        if isinstance(coefs, list) and coefs:
            out.append([float(c) for c in coefs])
    return out

def vec_mean(vs: list[list[float]]) -> list[float]:
    if not vs:
        return []
    n = len(vs)
    d = len(vs[0])
    out = [0.0] * d
    for v in vs:
        for i in range(d):
            out[i] += v[i]
    return [x / n for x in out]

def dot(a: list[float], b: list[float]) -> float:
    return sum(x * y for x, y in zip(a, b))

def norm(a: list[float]) -> float:
    return math.sqrt(dot(a, a))

def fit_poly(xs: list[float], ys: list[float], degree: int) -> tuple[list[float], float]:
    """Least-squares fit y = c[0] + c[1]*x + ... + c[degree]*x^degree.
    Returns (coeffs, R^2). Uses normal equations on numpy if available, else
    a small Gauss elimination for low degree."""
    n = len(xs)
    if n == 0:
        return ([0.0] * (degree + 1), 0.0)
    # Build Vandermonde
    X = [[x ** k for k in range(degree + 1)] for x in xs]
    # Normal eqs: A = X^T X, b = X^T y
    cols = degree + 1
    A = [[0.0] * cols for _ in range(cols)]
    b = [0.0] * cols
    for i in range(n):
        for r in range(cols):
            for c in range(cols):
                A[r][c] += X[i][r] * X[i][c]
            b[r] += X[i][r] * ys[i]
    # Gauss elim
    for i in range(cols):
        # pivot
        piv = i
        for k in range(i + 1, cols):
            if abs(A[k][i]) > abs(A[piv][i]):
                piv = k
        if piv != i:
            A[i], A[piv] = A[piv], A[i]
            b[i], b[piv] = b[piv], b[i]
        if abs(A[i][i]) < 1e-12:
            return ([0.0] * cols, 0.0)
        for k in range(i + 1, cols):
            f = A[k][i] / A[i][i]
            for c in range(i, cols):
                A[k][c] -= f * A[i][c]
            b[k] -= f * b[i]
    # back-sub
    coef = [0.0] * cols
    for i in range(cols - 1, -1, -1):
        s = b[i]
        for c in range(i + 1, cols):
            s -= A[i][c] * coef[c]
        coef[i] = s / A[i][i]
    # R^2
    y_mean = sum(ys) / n
    ss_tot = sum((y - y_mean) ** 2 for y in ys)
    ss_res = 0.0
    for x, y in zip(xs, ys):
        pred = sum(coef[k] * (x ** k) for k in range(cols))
        ss_res += (y - pred) ** 2
    r2 = 1.0 - (ss_res / ss_tot if ss_tot > 0 else 0.0)
    return coef, r2

def main() -> None:
    global DOMAIN_SUFFIX, WIN_SUFFIX, LOSE_SUFFIX
    ap = argparse.ArgumentParser()
    ap.add_argument("--domain-suffix", type=str, default="",
                    help="Read coefficients from <pair>_<outcome>_<suffix>/ instead of "
                         "<pair>_<outcome>/. Used to refit the dipole on pre-entry runs.")
    ap.add_argument("--win-domain-suffix", type=str, default=None,
                    help="Override domain suffix for winner dirs only.")
    ap.add_argument("--lose-domain-suffix", type=str, default=None,
                    help="Override domain suffix for loser dirs only.")
    args = ap.parse_args()
    DOMAIN_SUFFIX = args.domain_suffix.strip().lower()
    WIN_SUFFIX = args.win_domain_suffix.strip().lower() if args.win_domain_suffix is not None else None
    LOSE_SUFFIX = args.lose_domain_suffix.strip().lower() if args.lose_domain_suffix is not None else None
    if WIN_SUFFIX is not None or LOSE_SUFFIX is not None:
        print(f"[win{_win_suffix()}/, lose{_lose_suffix()}/]")
    elif DOMAIN_SUFFIX:
        print(f"[domain_suffix={DOMAIN_SUFFIX!r}] reading from <pair>_<outcome>{_suffix()}/")

    all_x_lin: list[float] = []  # pooled
    all_y_lin: list[float] = []
    all_x_quad: list[float] = []
    all_y_quad: list[float] = []
    rows = []
    print(f"{'pair':30s}  {'n_win':>5s}  {'n_lose':>6s}  {'R2_lin':>7s}  {'R2_quad':>8s}  alpha       beta        gamma")
    print("-" * 110)
    for pair in PAIRS:
        cw = load_coefs(f"{pair}_win{_win_suffix()}")
        cl = load_coefs(f"{pair}_lose{_lose_suffix()}")
        if not cw or not cl:
            print(f"{pair:30s}  {len(cw):>5d}  {len(cl):>6d}  --      --       (need both sides populated)")
            continue
        c_win_mean = vec_mean(cw)
        c_lose_mean = vec_mean(cl)
        nw = norm(c_win_mean) or 1.0
        nl = norm(c_lose_mean) or 1.0
        # Build per-trade scalars across ALL trades in this pair (winners + losers)
        xs: list[float] = []
        ys: list[float] = []
        for c in cw + cl:
            Ha = dot(c, c_win_mean) / nw
            Hb = dot(c, c_lose_mean) / nl
            xs.append(Ha * Hb)
            ys.append(Ha * Ha)
        # Linear fit: y = a + b*x
        coef_lin, r2_lin = fit_poly(xs, ys, 1)
        # Quadratic: y = a + b*x + c*x^2
        coef_q, r2_q = fit_poly(xs, ys, 2)
        a_q, b_q, c_q = coef_q
        rows.append((pair, len(cw), len(cl), r2_lin, r2_q, a_q, b_q, c_q))
        print(f"{pair:30s}  {len(cw):>5d}  {len(cl):>6d}  {r2_lin:>7.3f}  {r2_q:>8.3f}  {a_q:+.3e}  {b_q:+.3e}  {c_q:+.3e}")
        all_x_lin.extend(xs); all_y_lin.extend(ys)
        all_x_quad.extend(xs); all_y_quad.extend(ys)

    # Pooled fit
    if all_x_lin:
        _, r2_pool_lin = fit_poly(all_x_lin, all_y_lin, 1)
        _, r2_pool_q = fit_poly(all_x_quad, all_y_quad, 2)
        print("-" * 110)
        print(f"{'POOLED (all pairs)':30s}  {len(all_x_lin):>5d}  {'':>6s}  {r2_pool_lin:>7.3f}  {r2_pool_q:>8.3f}")

if __name__ == "__main__":
    main()
