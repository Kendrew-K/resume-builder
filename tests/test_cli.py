# tests/test_cli.py
# Run with `python -m pytest tests/test_cli.py` from the repo root — that
# puts the repo root on sys.path so both the `job_search` package and the
# root-level `job_search_cli.py` module import cleanly.
from job_search.posting import Posting
from job_search_cli import run_scrape, run_rank, run_top


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
        ("data analyst intern", "acme", "remote"): TrackerRow(
            company="Acme", title="Data Analyst Intern", location="Remote",
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


def test_run_scrape_excludes_already_handled_posting_seen_under_a_different_url(tmp_path):
    """Regression for Finding 1: a posting marked applied under its Indeed URL
    in a prior run must still be excluded when the same job resurfaces via
    LinkedIn under a different URL in a fresh scrape."""
    from job_search.tracker import TrackerRow, write_tracker
    output_path = tmp_path / "fall_2026_internships.md"
    tracker_path = tmp_path / "tracker.csv"
    write_tracker(tracker_path, {
        ("data analyst intern", "acme", "remote"): TrackerRow(
            company="Acme", title="Data Analyst Intern", location="Remote",
            url="https://indeed.example/999", status="applied",
            fit_score="0.5", date="2026-07-01")
    })

    def fake_linkedin(kw, loc, fetch=None):
        return [Posting(title="Data Analyst Intern", company="Acme", location="Remote",
                         url="https://li.example/different-url", source="linkedin",
                         fetched_date="2026-07-08")]

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


def test_run_ingest_merges_chrome_records_with_existing_md(tmp_path):
    """Browser-collected records merge into an existing scrape's output rather
    than replacing it, and the existing (github) URL wins dedupe."""
    import json

    from job_search_cli import run_ingest
    from job_search.markdown_output import write_internships_md

    output_path = tmp_path / "fall_2026_internships.md"
    tracker_path = tmp_path / "tracker.csv"
    write_internships_md(output_path, [
        Posting(title="Data Analyst Intern", company="Acme", location="Remote",
                url="https://acme.com/careers/1", source="github", fetched_date="2026-07-26"),
    ])
    dump = tmp_path / "chrome.json"
    dump.write_text(json.dumps([
        {"title": "Data Analyst Intern", "company": "ACME", "location": "remote",
         "url": "https://linkedin.com/jobs/view/1", "source": "linkedin"},
        {"title": "BI Intern", "company": "Globex", "location": "Remote",
         "url": "https://linkedin.com/jobs/view/2", "source": "linkedin"},
        {"title": "Far Away Intern", "company": "Other Co", "location": "Seattle, WA",
         "url": "https://linkedin.com/jobs/view/3", "source": "linkedin"},
        {"title": "", "company": "No Title Co", "location": "Remote",
         "url": "https://linkedin.com/jobs/view/4", "source": "linkedin"},
    ]), encoding="utf-8")

    postings, n = run_ingest(dump, tracker_path, output_path,
                             within_range=lambda loc: "remote" in loc.lower())

    assert n == 3  # the record missing a title is dropped
    by_title = {p.title: p for p in postings}
    assert set(by_title) == {"Data Analyst Intern", "BI Intern"}  # Seattle filtered out
    assert by_title["Data Analyst Intern"].url == "https://acme.com/careers/1"


def test_cached_posting_text_prefers_cache_and_falls_back(tmp_path):
    """A partial cache is still useful: cached URLs skip HTTP, missing ones
    (and cached-but-empty ones, e.g. a 429'd fetch) fall back to it."""
    import json

    from job_search_cli import cached_posting_text

    cache = tmp_path / "text.json"
    cache.write_text(json.dumps({
        "https://a.example/1": "cached description",
        "https://a.example/2": "",
    }), encoding="utf-8")

    fetch_text = cached_posting_text(cache, fetch_text=lambda url: f"http:{url}")

    assert fetch_text("https://a.example/1") == "cached description"
    assert fetch_text("https://a.example/2") == "http:https://a.example/2"
    assert fetch_text("https://a.example/3") == "http:https://a.example/3"


def test_run_applied_marks_tracker_so_scrape_drops_it(tmp_path):
    """A posting marked applied must not come back in a later scrape, even
    from a different source under a different URL."""
    from job_search_cli import filter_and_write, run_applied
    from job_search.markdown_output import write_internships_md

    output_path = tmp_path / "fall_2026_internships.md"
    tracker_path = tmp_path / "tracker.csv"
    write_internships_md(output_path, [
        Posting(title="Data Science Intern", company="Acme", location="Remote",
                url="https://acme.com/jobs/1", source="ats", fetched_date="2026-07-26",
                fit_score=0.5),
    ])

    missing = run_applied(output_path, tracker_path,
                          ["https://acme.com/jobs/1", "https://nope.example/9"])
    assert missing == ["https://nope.example/9"]

    same_job_elsewhere = Posting(title="data science intern", company="ACME",
                                 location="remote", url="https://linkedin.com/jobs/view/7",
                                 source="linkedin", fetched_date="2026-07-27")
    kept = filter_and_write([same_job_elsewhere], tracker_path, output_path,
                            within_range=lambda loc: True)
    assert kept == []


def test_run_applied_falls_back_to_tracker_when_posting_left_the_markdown(tmp_path):
    """After a posting reaches pending-review it is dropped from the markdown,
    so `applied <url>` has to flip the existing tracker row by URL instead."""
    from job_search_cli import run_applied
    from job_search.markdown_output import write_internships_md
    from job_search.tracker import TrackerRow, read_tracker, upsert, write_tracker
    from job_search.posting import posting_key

    output_path = tmp_path / "fall_2026_internships.md"
    tracker_path = tmp_path / "tracker.csv"
    write_internships_md(output_path, [])
    rows = {}
    upsert(rows, TrackerRow(company="Acme", title="Data Science Intern", location="Remote",
                            url="https://acme.com/jobs/1", status="pending-review",
                            fit_score="0.50", date="2026-07-26"))
    write_tracker(tracker_path, rows)

    assert run_applied(output_path, tracker_path, ["https://acme.com/jobs/1"]) == []
    row = read_tracker(tracker_path)[posting_key("Data Science Intern", "Acme", "Remote")]
    assert row.status == "applied"
    assert row.fit_score == "0.50"


def test_run_status_groups_rows_by_status(tmp_path):
    from job_search_cli import run_status
    from job_search.tracker import TrackerRow, upsert, write_tracker

    tracker_path = tmp_path / "tracker.csv"
    rows = {}
    for company, status in [("A", "applied"), ("B", "applied"), ("C", "pending-review")]:
        upsert(rows, TrackerRow(company=company, title="T", location="Remote",
                                url=f"https://{company}.example", status=status,
                                fit_score="0.5", date="2026-07-26"))
    write_tracker(tracker_path, rows)

    grouped = run_status(tracker_path)
    assert sorted(grouped) == ["applied", "pending-review"]
    assert len(grouped["applied"]) == 2


def test_run_top_orders_by_fit_and_sinks_unscored(tmp_path):
    output_path = tmp_path / "fall_2026_internships.md"
    from job_search.markdown_output import write_internships_md
    write_internships_md(output_path, [
        Posting(title="BI Intern", company="Northwind", location="Remote",
                url="https://example.com/1", source="ats", fetched_date="2026-07-08",
                fit_score=0.5),
        Posting(title="Unranked Intern", company="Nobody", location="Remote",
                url="https://example.com/2", source="ats", fetched_date="2026-07-08"),
        Posting(title="Data Science Intern", company="Acme", location="Remote",
                url="https://example.com/3", source="ats", fetched_date="2026-07-08",
                fit_score=0.9),
    ])

    top = run_top(output_path, limit=3)

    assert [p.company for p in top] == ["Acme", "Northwind", "Nobody"]
    assert run_top(output_path, limit=1)[0].fit_score == 0.9
