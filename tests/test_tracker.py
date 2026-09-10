from job_search.tracker import (TrackerRow, find_by_url, is_handled, read_tracker,
                                upsert, write_tracker)


def test_write_then_read_round_trips(tmp_path):
    path = tmp_path / "tracker.csv"
    rows = {}
    rows = upsert(rows, TrackerRow(company="Acme", title="Data Analyst Intern", location="Dallas, TX",
                                    url="https://example.com/1", status="pending-review",
                                    fit_score="0.55", date="2026-07-08"))
    write_tracker(path, rows)
    loaded = read_tracker(path)
    key = ("data analyst intern", "acme", "dallas, tx")
    assert loaded[key].company == "Acme"
    assert loaded[key].status == "pending-review"


def test_read_missing_file_returns_empty_dict(tmp_path):
    assert read_tracker(tmp_path / "does_not_exist.csv") == {}


def test_upsert_overwrites_same_posting_key():
    rows = {}
    rows = upsert(rows, TrackerRow(company="Acme", title="X", location="Dallas, TX",
                                    url="https://example.com/1", status="pending", fit_score="0.4",
                                    date="2026-07-08"))
    rows = upsert(rows, TrackerRow(company="Acme", title="X", location="Dallas, TX",
                                    url="https://example.com/1-alt-url", status="applied",
                                    fit_score="0.4", date="2026-07-09"))
    key = ("x", "acme", "dallas, tx")
    assert len(rows) == 1
    assert rows[key].status == "applied"
    assert rows[key].url == "https://example.com/1-alt-url"


def test_is_handled():
    rows = {}
    rows = upsert(rows, TrackerRow(company="A", title="T", location="Dallas, TX", url="u1",
                                    status="applied", fit_score="0.5", date="2026-07-08"))
    rows = upsert(rows, TrackerRow(company="A", title="T2", location="Dallas, TX", url="u2",
                                    status="pending", fit_score="0.5", date="2026-07-08"))
    assert is_handled(rows, "T", "A", "Dallas, TX") is True
    assert is_handled(rows, "T2", "A", "Dallas, TX") is False
    assert is_handled(rows, "Unknown", "A", "Dallas, TX") is False


def test_is_handled_matches_across_different_urls_for_same_posting():
    """A posting marked applied under one URL must still be recognized as
    handled when it resurfaces under a different URL from another source
    (the scenario Finding 1 fixes)."""
    rows = {}
    rows = upsert(rows, TrackerRow(company="Acme", title="Data Analyst Intern", location="Remote",
                                    url="https://indeed.example/1", status="applied",
                                    fit_score="0.5", date="2026-07-01"))
    assert is_handled(rows, "Data Analyst Intern", "Acme", "Remote") is True
    assert is_handled(rows, "DATA ANALYST INTERN", "acme", "remote") is True


def test_is_handled_covers_in_progress_statuses():
    """pending-review/needs-manual postings were already worked once, so they
    must not be re-queued and re-applied to on the next run."""
    rows = {}
    for status in ("pending-review", "needs-manual"):
        upsert(rows, TrackerRow(company=status, title="T", location="Remote",
                                url="https://example.com/x", status=status,
                                fit_score="0.5", date="2026-01-01"))
        assert is_handled(rows, "T", status, "Remote") is True

    upsert(rows, TrackerRow(company="Fresh", title="T", location="Remote",
                            url="https://example.com/y", status="pending",
                            fit_score="0.5", date="2026-01-01"))
    assert is_handled(rows, "T", "Fresh", "Remote") is False


def test_find_by_url():
    rows = {}
    upsert(rows, TrackerRow(company="Acme", title="T", location="Remote",
                            url="https://example.com/1", status="pending-review",
                            fit_score="0.5", date="2026-01-01"))
    assert find_by_url(rows, "https://example.com/1").company == "Acme"
    assert find_by_url(rows, "https://example.com/missing") is None
