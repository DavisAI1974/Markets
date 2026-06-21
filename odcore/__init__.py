"""
odcore — Operator-Discovery signal core for the Markets platform.

This package rebuilds the trading signal core around the Operator-Discovery (OD)
methodology recorded in the master research log (CLAUDE (5).md). The crude
order-flow-imbalance "dipole" the rest of the repo uses is superseded here by the
real OD machinery:

    operators.py   - windowed operator basis [H_a, H_b, H_a^2, H_b^2, H_a*H_b, MI]
    null_extract.py- centered-SVD null extraction + coupling decomposition + strength meters
    (later)        - leadlag, dipole_predictor, symbolic (PySR), coupling_scanner, stacking,
                     validation, sizing, generators, channels, io

ALL equations here are RECONSTRUCTED-FROM-CLAUDE.md (the original scripts live in the
separate basic_equations / agent repo, not reachable from this session). Each module
header names the original script it would be a verbatim port of, so the originals can
be diffed in later if that repo is added to scope.
"""

__all__ = ["operators", "null_extract"]
