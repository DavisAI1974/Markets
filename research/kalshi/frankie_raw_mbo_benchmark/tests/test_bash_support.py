"""The workflow fixture must execute the exact Bash text on either host platform."""
import unittest

from research.kalshi.frankie_raw_mbo_benchmark.tests.bash_support import run_bash


class BashSupportTests(unittest.TestCase):
    def test_preserves_quoted_awk_and_heredoc_text(self):
        result = run_bash("""awk '$3=="part" {print $1}' <<'ROWS'
/dev/example 123 part
/dev/other 456 disk
ROWS
""")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, "/dev/example\n")

    def test_syntax_check_rejects_malformed_script(self):
        result = run_bash("if true; then\n", syntax_only=True)
        self.assertNotEqual(result.returncode, 0)

    def test_syntax_check_does_not_execute_script(self):
        result = run_bash("echo SHOULD_NOT_RUN\nexit 37\n", syntax_only=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, "")
