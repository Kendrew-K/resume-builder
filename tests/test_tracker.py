from job_search.tracker import TrackerRow, read_tracker, write_tracker, upsert, is_handled


def test_write_then_read_round_trips(tmp_path):
    path = tmp_path / "tracker.csv"
    rows = {}
    rows = upsert(rows, TrackerRow(company="Acme", title="Data Analyst Intern",
                                    url="https://example.com/1", status="pending-review",
                                    fit_score="0.55", date="2026-07-08"))
    write_tracker(path, rows)
    loaded = read_tracker(path)
    assert loaded["https://example.com/1"].company == "Acme"
    assert loaded["https://example.com/1"].status == "pending-review"


def test_read_missing_file_returns_empty_dict(tmp_path):
    assert read_tracker(tmp_path / "does_not_exist.csv") == {}


def test_upsert_overwrites_same_url():
    rows = {}
    rows = upsert(rows, TrackerRow(company="Acme", title="X", url="https://example.com/1",
                                    status="pending", fit_score="0.4", date="2026-07-08"))
    rows = upsert(rows, TrackerRow(company="Acme", title="X", url="https://example.com/1",
                                    status="applied", fit_score="0.4", date="2026-07-09"))
    assert len(rows) == 1
    assert rows["https://example.com/1"].status == "applied"


def test_is_handled():
    rows = {}
    rows = upsert(rows, TrackerRow(company="A", title="T", url="u1", status="applied",
                                    fit_score="0.5", date="2026-07-08"))
    rows = upsert(rows, TrackerRow(company="A", title="T", url="u2", status="needs-manual",
                                    fit_score="0.5", date="2026-07-08"))
    assert is_handled(rows, "u1") is True
    assert is_handled(rows, "u2") is False
    assert is_handled(rows, "unknown-url") is False
