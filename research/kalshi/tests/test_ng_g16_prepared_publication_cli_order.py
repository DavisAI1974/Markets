import sys
import unittest
from unittest.mock import patch

from research.kalshi.ng_g16_prepared_publication_gate import (
    G16PreparedPublicationError,
    main,
)


class G16PreparedPublicationCliOrderTests(unittest.TestCase):
    def test_actual_outcome_file_is_not_read_when_curve_lock_fails(self):
        names = (
            "prepared-curve-authorization",
            "prepared-causal-authorization",
            "prepared-gate",
            "prepared-index",
            "manifest",
            "replay",
            "blind-prior",
            "causal-completion",
            "shadow-plan",
            "authorization-stream",
            "posterior-stream",
            "blind",
            "blind-safe-state",
            "registry",
            "refined",
            "adjudication",
            "actual",
            "blind-score",
            "refined-score",
            "comparison",
            "chronological-validation",
            "blind-rt",
            "refined-rt",
            "blind-png",
            "refined-png",
            "curve-lock-out",
            "out",
        )
        argv = ["ng_g16_prepared_publication_gate.py"]
        for name in names:
            argv.extend((f"--{name}", f"/{name}.json"))

        reads = []

        def read_bytes(path):
            observed = str(path)
            reads.append(observed)
            if observed in {"/blind.json", "/refined.json"}:
                return b"{}"
            raise AssertionError(f"unexpected pre-lock file read: {observed}")

        with patch.object(sys, "argv", argv), patch(
            "research.kalshi.ng_g16_prepared_publication_gate.Path.read_bytes",
            read_bytes,
        ), patch(
            "research.kalshi.ng_g16_prepared_publication_gate._load",
            return_value={},
        ), patch(
            "research.kalshi.ng_g16_prepared_publication_gate.build_curve_lock",
            side_effect=G16PreparedPublicationError("curve lock failed"),
        ):
            with self.assertRaises(G16PreparedPublicationError):
                main()

        self.assertEqual(reads, ["/blind.json", "/refined.json"])
        self.assertNotIn("/actual.json", reads)


if __name__ == "__main__":
    unittest.main()
