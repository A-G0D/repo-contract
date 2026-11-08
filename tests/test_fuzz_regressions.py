"""Regressions found by the stdlib fuzz run (seed 20261108): hostile inputs must be reported, not crash."""

import os
import shutil
import subprocess
import tempfile
import unittest

from repo_contract.contract import build_contract, detect_remote
from repo_contract.policy import load_patterns


class DeepPatternsFileTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="rc-fuzz-")
        self.addCleanup(shutil.rmtree, self.dir, True)

    def _write(self, data: bytes) -> str:
        path = os.path.join(self.dir, "patterns.json")
        with open(path, "wb") as fh:
            fh.write(data)
        return path

    def test_deeply_nested_json_is_value_error(self):
        path = self._write(b"[" * 100_000)
        with self.assertRaises(ValueError):
            load_patterns(path)

    def test_deeply_nested_json_object_is_value_error(self):
        path = self._write(b'[{"category": ' * 40_000)
        with self.assertRaises(ValueError):
            load_patterns(path)

    def test_deeply_nested_regex_is_value_error(self):
        path = self._write(b'[{"category": "disclosure", "pattern": "' + b"(" * 5000 + b'"}]')
        with self.assertRaises(ValueError):
            load_patterns(path)


class BadRemoteUrlTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="rc-fuzz-")
        self.addCleanup(shutil.rmtree, self.dir, True)
        try:
            subprocess.run(["git", "-C", self.dir, "init", "-q"], check=True, timeout=30)
        except (OSError, subprocess.SubprocessError) as exc:
            self.skipTest(f"git unavailable: {exc}")

    def test_unparseable_origin_url_does_not_crash(self):
        subprocess.run(
            ["git", "-C", self.dir, "remote", "add", "origin", "http://[::1"],
            check=True,
            timeout=30,
        )
        self.assertEqual(detect_remote(self.dir), "")
        build_contract(self.dir)


if __name__ == "__main__":
    unittest.main()
