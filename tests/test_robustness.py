"""Robustness: messy repositories must scan cleanly instead of hanging or crashing."""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@unittest.skipUnless(hasattr(os, "mkfifo"), "needs named pipes")
class FifoDocTest(unittest.TestCase):
    def test_fifo_named_like_doc_does_not_hang_scan(self):
        with tempfile.TemporaryDirectory() as tmp:
            os.mkfifo(os.path.join(tmp, "CONTRIBUTING.md"))
            env = dict(os.environ, PYTHONPATH=REPO_ROOT)
            proc = subprocess.run(
                [sys.executable, "-m", "repo_contract", "scan", "--repo", tmp, "--format", "json"],
                cwd=REPO_ROOT,
                env=env,
                capture_output=True,
                text=True,
                timeout=20,
            )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertNotIn("Traceback", proc.stderr)


if __name__ == "__main__":
    unittest.main()
