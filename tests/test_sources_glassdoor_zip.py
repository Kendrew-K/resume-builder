from job_search.sources import fetch_glassdoor, fetch_ziprecruiter

GLASSDOOR_AUTOCOMPLETE = '[{"id":1139977,"locationId":1139977,"locationType":"C","locationName":"Dallas, TX","label":"Dallas, TX"}]'

GLASSDOOR_SEARCH = """
<a class="JobCard_jobTitle__GLyJ1" data-test="job-title" href="https://www.glassdoor.com/job-listing/data-analyst-intern-acme-JV_IC1.htm?jl=111">Data Analyst Intern</a>
<div class="EmployerProfile_compactEmployerName__abc12">Acme Corp</div>
<div class="JobCard_location__Ds1fM">Dallas, TX</div>
<a class="JobCard_jobTitle__GLyJ1" data-test="job-title" href="https://www.glassdoor.com/job-listing/bi-intern-widgets-JV_IC2.htm?jl=222">BI Intern</a>
<div class="EmployerProfile_compactEmployerName__abc12">Widgets Inc</div>
<div class="JobCard_location__Ds1fM">Remote</div>
"""

ZIPRECRUITER_CHALLENGE = '<!DOCTYPE html><html><head><title>Just a moment...</title></head><body>cf-challenge</body></html>'


def test_fetch_glassdoor_two_step_parses_fixture():
    calls = []

    def fake_fetch(url):
        calls.append(url)
        if "autocomplete/location" in url:
            return GLASSDOOR_AUTOCOMPLETE
        return GLASSDOOR_SEARCH

    postings = fetch_glassdoor("Data Analyst Intern", "Dallas, TX", fetch=fake_fetch)
    assert len(calls) == 2
    assert "autocomplete/location" in calls[0]
    assert "locId=1139977" in calls[1]
    assert len(postings) == 2
    assert postings[0].title == "Data Analyst Intern"
    assert postings[0].company == "Acme Corp"
    assert postings[0].url == "https://www.glassdoor.com/job-listing/data-analyst-intern-acme-JV_IC1.htm"
    assert postings[0].source == "glassdoor"
    assert postings[1].location == "Remote"


def test_fetch_glassdoor_returns_empty_when_location_unresolved():
    postings = fetch_glassdoor("x", "nowhere", fetch=lambda url: "[]")
    assert postings == []


def test_fetch_ziprecruiter_degrades_on_cloudflare_challenge():
    postings = fetch_ziprecruiter("Data Analyst Intern", "Dallas, TX",
                                   fetch=lambda url: ZIPRECRUITER_CHALLENGE)
    assert postings == []


def test_fetch_ziprecruiter_returns_empty_on_fetch_failure():
    def boom(url):
        raise TimeoutError("blocked")
    assert fetch_ziprecruiter("x", "y", fetch=boom) == []
