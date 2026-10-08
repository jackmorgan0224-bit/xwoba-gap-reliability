"""Run the SQL validation checks as tests. Requires data/raw/ (run src/fetch_data.py first)."""

from pathlib import Path

import duckdb
import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def check_results(tmp_path_factory, monkeypatch_module):
    monkeypatch_module.chdir(ROOT)  # SQL reads data/raw/ relative to the repo root
    con = duckdb.connect(str(tmp_path_factory.mktemp("db") / "test.duckdb"))
    con.execute((ROOT / "sql" / "01_build_tables.sql").read_text(encoding="utf-8"))
    return con.execute((ROOT / "sql" / "02_validation.sql").read_text(encoding="utf-8")).fetchall()


@pytest.fixture(scope="module")
def monkeypatch_module():
    with pytest.MonkeyPatch.context() as mp:
        yield mp


def test_no_failed_checks(check_results):
    failures = [f"{name}: {flagged}/{checked}" for _, name, flagged, checked, result in check_results
                if result == "FAIL"]
    assert not failures, "Validation failures:\n" + "\n".join(failures)


def test_warnings_stay_small(check_results):
    """WARN checks are allowed a handful of known rows (see docs/data_notes.md), not a trend."""
    warnings = [(name, flagged, checked) for _, name, flagged, checked, result in check_results
                if result == "WARN"]
    for name, flagged, checked in warnings:
        assert flagged / checked < 0.01, f"{name}: {flagged}/{checked} flagged"
