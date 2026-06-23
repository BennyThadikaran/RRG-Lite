"""Tests for utils.load_config.

The previous implementation grepped sys.argv with `"-c" in sys.argv` and
assumed the next token was the config path. That worked for the common
`-c foo.json` case, but three real invocations silently fell through to the
default `user.json`:

1. `-cfoo.json` — argparse would split this into a `-c` flag and the value
   `foo.json`, but the raw sys.argv substring check only matched when `-c`
   appeared as a standalone token.
2. `--config=foo.json` — the long form with `=` is never present as a
   standalone `--config` token, so the check missed it entirely.
3. `-c` with no following argument — the old code took the NEXT argv item
   as the path, even when it was a positional argument (e.g. a stock symbol)
   or another flag.

Using argparse to resolve the config path fixes all three: argparse parses
`-c foo.json`, `-cfoo.json`, `--config foo.json`, and `--config=foo.json`
uniformly, and rejects `-c` with no value (exiting with a usage error
instead of silently reading the wrong file).

Also, the old function returned `None` when the resolved path did not
exist (e.g. because `-c` pointed at a missing file). argparse won't fall
back to the default once `-c` is given, so an explicit-but-missing path
must raise rather than silently reading `user.json`. The tests below
pin both behaviors.
"""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

# Make the parent dir importable so `import utils` works when running
# `python3 tests/test_utils.py` directly (the original package has no
# setup.py / pyproject.toml).
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import utils  # noqa: E402


class TestLoadConfig(unittest.TestCase):
    def _write_json(self, tmpdir: Path, contents: dict) -> Path:
        p = tmpdir / "cfg.json"
        p.write_text(json.dumps(contents))
        return p

    def test_no_args_returns_none_when_default_missing(self):
        # When no `-c` is supplied and the default user.json does not exist
        # alongside utils.py, the function must return None (so init.py can
        # print its "Configuration file is missing." message).
        with mock.patch.object(Path, "exists", return_value=False):
            result = utils.load_config(argv=[])
        self.assertIsNone(result)

    def test_long_form_with_equals_is_recognized(self):
        # `--config=foo.json` — the old substring check missed this entirely
        # because "--config" never appears as a standalone argv token.
        with tempfile.TemporaryDirectory() as tmp:
            tmpdir = Path(tmp)
            cfg = self._write_json(tmpdir, {"LOADER": "EODFileLoader", "X": 1})
            with mock.patch.object(Path, "exists", return_value=True):
                result = utils.load_config(argv=[f"--config={cfg}"])
        self.assertEqual(result, {"LOADER": "EODFileLoader", "X": 1})

    def test_short_form_glued_to_value_is_recognized(self):
        # `-cfoo.json` — argparse splits this into a `-c` flag and value
        # `foo.json`, but the old `"-c" in sys.argv` check only fired when
        # `-c` appeared as a standalone argv token.
        with tempfile.TemporaryDirectory() as tmp:
            tmpdir = Path(tmp)
            cfg = self._write_json(tmpdir, {"LOADER": "EODFileLoader", "X": 2})
            with mock.patch.object(Path, "exists", return_value=True):
                result = utils.load_config(argv=[f"-c{cfg}"])
        self.assertEqual(result, {"LOADER": "EODFileLoader", "X": 2})

    def test_explicit_path_missing_does_not_fall_back_to_default(self):
        # Once `-c` is given, argparse won't fall back to the default
        # user.json. argparse would normally print a usage error when the
        # path doesn't exist, but since we resolve the path ourselves after
        # parsing (we just want the value, not to enforce existence at
        # parse-time), the function must still raise / return None rather
        # than silently reading the default. We assert it does not return
        # the contents of a hypothetical default user.json.
        with tempfile.TemporaryDirectory() as tmp:
            tmpdir = Path(tmp)
            cfg = tmpdir / "does-not-exist.json"
            # Patch exists to return False (the file is genuinely missing).
            with mock.patch.object(Path, "exists", return_value=False):
                result = utils.load_config(argv=[str(cfg)])
        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
