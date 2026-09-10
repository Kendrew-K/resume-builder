# tests/test_ats.py
# Run with `python -m pytest tests/test_ats.py` from the repo root.
import json

from job_search import ats


def test_board_slugs_reads_every_ats_host_out_of_listing_urls():
    listings = json.dumps([
        {"url": "https://job-boards.greenhouse.io/Airbnb/jobs/123"},
        {"url": "https://boards.greenhouse.io/stripe/jobs/456"},
        {"url": "https://jobs.lever.co/netflix/abc-def"},
        {"url": "https://jobs.ashbyhq.com/ramp/xyz?utm=1"},
        {"url": "https://example.com/careers/789"},  # not an ATS we poll
        {},                                          # listing with no url
    ])
    assert ats.board_slugs(listings) == {
        "greenhouse": {"airbnb", "stripe"},  # host casing normalized
        "lever": {"netflix"},
        "ashby": {"ramp"},
    }


def test_board_slugs_degrades_to_empty_on_bad_json():
    assert ats.board_slugs("not json") == {}


def test_ashby_keeps_only_internships_and_flags_remote(monkeypatch):
    monkeypatch.setattr(ats, "_get_json", lambda url, timeout=20: {"jobs": [
        {"title": "Data Science Intern", "jobUrl": "https://jobs.ashbyhq.com/acme/1",
         "location": "Dallas, TX", "isRemote": False, "descriptionPlain": "  do   data <b>work</b> "},
        {"title": "Senior Data Scientist", "jobUrl": "https://jobs.ashbyhq.com/acme/2",
         "location": "Dallas, TX", "descriptionPlain": "not an internship"},
        {"title": "Analytics Co-Op", "jobUrl": "https://jobs.ashbyhq.com/acme/3",
         "location": "New York, NY", "isRemote": True, "descriptionPlain": "co-op"},
    ]})
    results = ats._ashby("acme")

    assert [p.title for p, _ in results] == ["Data Science Intern", "Analytics Co-Op"]
    assert results[0][1] == "do data work"  # tags stripped, whitespace collapsed
    assert results[1][0].location == "New York, NY (Remote)"


def test_fetch_ats_matches_keyword_tokens_and_descriptions_pair_by_url(monkeypatch):
    from job_search.posting import Posting

    def posting(title, url):
        return Posting(title=title, company="Acme", location="Remote", url=url,
                       source="ashby", fetched_date="2026-07-26")

    monkeypatch.setattr(ats, "_poll_all_boards", lambda: (
        (posting("Data Science Intern", "https://a.example/1"), "desc one"),
        (posting("Marketing Intern", "https://a.example/2"), ""),
    ))

    assert [p.title for p in ats.fetch_ats("Data Science Intern", "Remote")] == ["Data Science Intern"]
    assert ats.fetch_ats("BI Intern", "Remote") == []
    # postings with no description are left out of the rank text cache
    assert ats.descriptions() == {"https://a.example/1": "desc one"}
