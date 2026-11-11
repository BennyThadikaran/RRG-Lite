"""Tests for watchlist-file handling in init.py.

A `-f/--file` path that does not exist must produce a clean error message
and a nonzero exit, not an unhandled `FileNotFoundError` traceback from
`Path.read_text()`.
"""

import json
import subprocess
import sys
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parent.parent / "src"


def _run_init(argv, cwd=SRC_DIR):
    return subprocess.run(
        [sys.executable, "init.py", *argv],
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=180,
    )


def _write_config(tmp_path, benchmark=None):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    config = {"DATA_PATH": str(data_dir), "LOADER": "EODFileLoader"}
    if benchmark is not None:
        config["BENCHMARK"] = benchmark
    cfg = tmp_path / "user.json"
    cfg.write_text(json.dumps(config))
    return cfg


def test_missing_watchlist_file_is_clean_error(tmp_path):
    cfg = _write_config(tmp_path)
    missing = tmp_path / "no-such-watchlist.txt"

    proc = _run_init(["-c", str(cfg), "-f", str(missing)])

    assert proc.returncode != 0
    assert "Traceback" not in proc.stderr
    assert "Watchlist file not found" in proc.stderr
    assert str(missing) in proc.stderr


def test_existing_watchlist_file_gets_past_loading(tmp_path):
    """A present watchlist file must not trigger the missing-file error;
    execution proceeds past file loading into data loading (which fails
    here only because the temp DATA_PATH has no benchmark data)."""
    cfg = _write_config(tmp_path, benchmark="NIFTY")
    watchlist = tmp_path / "watchlist.txt"
    watchlist.write_text("AAPL\n")

    proc = _run_init(["-c", str(cfg), "-f", str(watchlist)])

    assert "Watchlist file not found" not in proc.stderr
    assert "Unable to load benchmark data" in proc.stderr
