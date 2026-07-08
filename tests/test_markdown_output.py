from job_search.posting import Posting
from job_search.markdown_output import write_internships_md, parse_internships_md


def _p(fit_score=None, rationale=None):
    return Posting(title="Data Analyst Intern", company="Acme Corp", location="Dallas, TX",
                    url="https://example.com/1", source="linkedin", fetched_date="2026-07-08",
                    fit_score=fit_score, rationale=rationale)


def test_round_trip_without_scores(tmp_path):
    path = tmp_path / "internships.md"
    write_internships_md(path, [_p()])
    loaded = parse_internships_md(path)
    assert len(loaded) == 1
    assert loaded[0].title == "Data Analyst Intern"
    assert loaded[0].company == "Acme Corp"
    assert loaded[0].location == "Dallas, TX"
    assert loaded[0].url == "https://example.com/1"
    assert loaded[0].source == "linkedin"
    assert loaded[0].fetched_date == "2026-07-08"
    assert loaded[0].fit_score is None


def test_round_trip_with_scores(tmp_path):
    path = tmp_path / "internships.md"
    write_internships_md(path, [_p(fit_score=0.55, rationale="Strong SQL/Python overlap")])
    loaded = parse_internships_md(path)
    assert loaded[0].fit_score == 0.55
    assert loaded[0].rationale == "Strong SQL/Python overlap"


def test_sorted_highest_fit_first(tmp_path):
    path = tmp_path / "internships.md"
    low = Posting(title="Low Fit", company="B", location="Remote", url="u2",
                   source="indeed", fetched_date="2026-07-08", fit_score=0.2)
    high = Posting(title="High Fit", company="A", location="Remote", url="u1",
                    source="indeed", fetched_date="2026-07-08", fit_score=0.8)
    write_internships_md(path, [low, high])
    loaded = parse_internships_md(path)
    assert loaded[0].title == "High Fit"
    assert loaded[1].title == "Low Fit"


def test_fit_score_round_trips_exactly_at_the_threshold_boundary(tmp_path):
    """Regression for Finding 3: a score just below the 30% cutoff must not
    round up to 0.30 on write, or rank's qualifying count (computed on the
    true in-memory float) would disagree with a later re-parse of this file
    (e.g. by the apply playbook), which would wrongly include the posting."""
    path = tmp_path / "internships.md"
    write_internships_md(path, [_p(fit_score=0.296)])
    loaded = parse_internships_md(path)
    assert loaded[0].fit_score == 0.296
    assert "0.30" not in path.read_text(encoding="utf-8")


def test_pipe_escape_in_title_and_fields(tmp_path):
    """Test that pipe characters in title, company, location, url are escaped for markdown tables."""
    path = tmp_path / "internships.md"
    # Create posting with pipes in multiple fields
    posting = Posting(
        title="Data Analyst Intern | Fall 2026",
        company="Acme | Tech Corp",
        location="Dallas | Remote",
        url="https://example.com/job?param=a|b",
        source="linkedin",
        fetched_date="2026-07-08",
        fit_score=0.75,
        rationale="Good fit | SQL match"
    )
    write_internships_md(path, [posting])
    loaded = parse_internships_md(path)

    # Verify that pipes are escaped with forward slashes in round-trip
    assert len(loaded) == 1
    assert loaded[0].title == "Data Analyst Intern / Fall 2026"
    assert loaded[0].company == "Acme / Tech Corp"
    assert loaded[0].location == "Dallas / Remote"
    assert loaded[0].url == "https://example.com/job?param=a/b"
    assert loaded[0].rationale == "Good fit / SQL match"
    assert loaded[0].fit_score == 0.75
