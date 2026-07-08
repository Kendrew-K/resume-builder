# tests/test_cli.py
# Run with `python -m pytest tests/test_cli.py` from the repo root — that
# puts the repo root on sys.path so both the `job_search` package and the
# root-level `job_search_cli.py` module import cleanly.
from job_search.posting import Posting
from job_search_cli import run_scrape, run_rank


def test_run_scrape_dedupes_filters_and_writes(tmp_path):
    output_path = tmp_path / "fall_2026_internships.md"
    tracker_path = tmp_path / "tracker.csv"

    def fake_linkedin(kw, loc, fetch=None):
        return [Posting(title="Data Analyst Intern", company="Acme", location="Remote",
                         url="https://li.example/1", source="linkedin", fetched_date="2026-07-08")]

    def fake_indeed(kw, loc, fetch=None):
        return [Posting(title="Data Analyst Intern", company="ACME", location="remote",
                         url="https://indeed.example/1", source="indeed", fetched_date="2026-07-08"),
                Posting(title="Far Away Intern", company="Other Co", location="Seattle, WA",
                         url="https://indeed.example/2", source="indeed", fetched_date="2026-07-08")]

    def empty(kw, loc, fetch=None):
        return []

    def fake_within_range(location, fetch=None):
        return "remote" in location.lower()

    postings, blocked = run_scrape(
        source_fns=[("linkedin", fake_linkedin), ("indeed", fake_indeed),
                    ("glassdoor", empty), ("ziprecruiter", empty)],
        keywords=["Data Analyst Intern"], locations=["Remote"],
        tracker_path=tracker_path, output_path=output_path,
        within_range=fake_within_range,
    )
    assert len(postings) == 1  # deduped (same title/company/location) and Seattle filtered out
    assert postings[0].url == "https://li.example/1"
    assert "glassdoor" in blocked
    assert "ziprecruiter" in blocked
    assert output_path.exists()


def test_run_scrape_excludes_already_handled(tmp_path):
    from job_search.tracker import TrackerRow, write_tracker
    output_path = tmp_path / "fall_2026_internships.md"
    tracker_path = tmp_path / "tracker.csv"
    write_tracker(tracker_path, {
        "https://li.example/1": TrackerRow(company="Acme", title="Data Analyst Intern",
                                            url="https://li.example/1", status="applied",
                                            fit_score="0.5", date="2026-07-01")
    })

    def fake_linkedin(kw, loc, fetch=None):
        return [Posting(title="Data Analyst Intern", company="Acme", location="Remote",
                         url="https://li.example/1", source="linkedin", fetched_date="2026-07-08")]

    def empty(kw, loc, fetch=None):
        return []

    postings, _ = run_scrape(
        source_fns=[("linkedin", fake_linkedin), ("indeed", empty),
                    ("glassdoor", empty), ("ziprecruiter", empty)],
        keywords=["Data Analyst Intern"], locations=["Remote"],
        tracker_path=tracker_path, output_path=output_path,
        within_range=lambda loc, fetch=None: True,
    )
    assert postings == []


def test_run_rank_scores_and_rewrites(tmp_path):
    output_path = tmp_path / "fall_2026_internships.md"
    experiences_path = tmp_path / "experiences.md"
    experiences_path.write_text("Skilled in SQL and Python.", encoding="utf-8")
    from job_search.markdown_output import write_internships_md
    write_internships_md(output_path, [
        Posting(title="Data Analyst Intern", company="Acme", location="Remote",
                url="https://example.com/1", source="linkedin", fetched_date="2026-07-08"),
    ])

    def fake_fetch_text(url, fetch=None):
        return "Requires SQL, Python, Tableau, and AWS."

    postings, qualifying = run_rank(output_path, experiences_path, fetch_text=fake_fetch_text)
    assert postings[0].fit_score == 0.5
    assert qualifying == 1  # 0.5 >= 0.30
