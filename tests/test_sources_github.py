import json

from job_search.sources import fetch_github_internships

LISTINGS = json.dumps([
    {
        "company_name": "Acme Corp", "title": "Data Analytics Intern",
        "active": True, "terms": ["Fall 2026"],
        "url": "https://acme.greenhouse.io/jobs/1",
        "locations": ["Dallas, TX", "New York, NY"],
    },
    {
        "company_name": "Widgets Inc", "title": "BI Intern",
        "active": True, "terms": ["Fall 2026"],
        "url": "https://widgets.lever.co/2",
        "locations": ["Remote in USA"],
    },
    {
        "company_name": "Stale Co", "title": "Data Science Intern",
        "active": False, "terms": ["Fall 2026"],
        "url": "https://stale.co/3", "locations": ["Dallas, TX"],
    },
    {
        "company_name": "Summer Co", "title": "Data Intern",
        "active": True, "terms": ["Summer 2026"],
        "url": "https://summer.co/4", "locations": ["Dallas, TX"],
    },
    {
        "company_name": "Robots Inc", "title": "Mechanical Engineering Intern",
        "active": True, "terms": ["Fall 2026"],
        "url": "https://robots.co/5", "locations": ["Dallas, TX"],
    },
])


def test_matches_keyword_tokens_and_expands_locations():
    postings = fetch_github_internships("Data Analyst Intern", "Dallas, TX",
                                        fetch=lambda url: LISTINGS)
    # Acme matches on "data" (one posting per location); others filtered:
    # Stale inactive, Summer wrong term, Robots no keyword token.
    assert [(p.company, p.location) for p in postings] == [
        ("Acme Corp", "Dallas, TX"), ("Acme Corp", "New York, NY"),
    ]
    assert postings[0].source == "github"
    assert postings[0].url == "https://acme.greenhouse.io/jobs/1"


def test_bi_keyword_matches_whole_word_only():
    postings = fetch_github_internships("BI Intern", "Remote", fetch=lambda url: LISTINGS)
    # "bi" must not substring-match "Mechanical"... or "Analytics".
    assert [p.company for p in postings] == ["Widgets Inc"]


def test_fetch_failure_degrades_to_empty():
    def boom(url):
        raise OSError("network down")
    assert fetch_github_internships("Data Intern", "Dallas, TX", fetch=boom) == []
