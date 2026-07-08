# tests/test_posting.py
from job_search.posting import Posting, dedupe_postings


def _p(title="Data Analyst Intern", company="Acme Corp", location="Dallas, TX",
       url="https://example.com/1", source="linkedin", fetched="2026-07-08"):
    return Posting(title=title, company=company, location=location, url=url,
                    source=source, fetched_date=fetched)


def test_dedupe_removes_case_insensitive_duplicate_across_sources():
    a = _p(source="linkedin", url="https://linkedin.com/jobs/view/1")
    b = _p(source="indeed", url="https://indeed.com/viewjob?jk=2",
           title="DATA ANALYST INTERN", company="acme corp", location="dallas, tx")
    result = dedupe_postings([a, b])
    assert len(result) == 1
    assert result[0] is a


def test_dedupe_keeps_distinct_postings():
    a = _p(title="Data Analyst Intern", company="Acme Corp")
    b = _p(title="BI Intern", company="Widgets Inc")
    result = dedupe_postings([a, b])
    assert len(result) == 2
