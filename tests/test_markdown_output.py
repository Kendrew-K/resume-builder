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
