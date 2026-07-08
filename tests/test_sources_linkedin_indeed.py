from job_search.sources import fetch_linkedin, fetch_indeed, fetch_posting_text

LINKEDIN_FIXTURE = """
<div class="base-card" data-entity-urn="urn:li:jobPosting:1">
  <a class="base-card__full-link absolute top-0 right-0 bottom-0 left-0 p-0 z-[2] outline-offset-[4px]" href="https://www.linkedin.com/jobs/view/data-analyst-intern-at-acme-4437848829?position=1&pageNum=0">
  </a>
  <h3 class="base-search-card__title">
      Data Analyst Intern
  </h3>
  <h4 class="base-search-card__subtitle">
    <a class="hidden-nested-link">
            Acme Corp
          </a>
  </h4>
  <span class="job-search-card__location">
          Dallas, TX
          </span>
</div>
<div class="base-card" data-entity-urn="urn:li:jobPosting:3">
  <a class="base-card__full-link absolute top-0 right-0 bottom-0 left-0 p-0 z-[2] outline-offset-[4px]" href="https://www.linkedin.com/jobs/view/no-company-page-intern-4437848831?position=3&pageNum=0">
  </a>
  <h3 class="base-search-card__title">
      No Company Page Intern
  </h3>
  <h4 class="base-search-card__subtitle">
          Stealth Startup (no company page, so no nested &lt;a&gt; link)
  </h4>
  <span class="job-search-card__location">
          Austin, TX
          </span>
</div>
<div class="base-card" data-entity-urn="urn:li:jobPosting:2">
  <a class="base-card__full-link absolute top-0 right-0 bottom-0 left-0 p-0 z-[2] outline-offset-[4px]" href="https://www.linkedin.com/jobs/view/bi-intern-at-widgets-4437848830?position=2&pageNum=0">
  </a>
  <h3 class="base-search-card__title">
      BI Intern
  </h3>
  <h4 class="base-search-card__subtitle">
    <a class="hidden-nested-link">
            Widgets Inc
          </a>
  </h4>
  <span class="job-search-card__location">
          Remote
          </span>
</div>
"""

INDEED_FIXTURE = """<!doctype html><html><head><title>Data Analyst Intern Jobs, Employment in Dallas, TX | Indeed</title></head>
<body>
<script>
window.mosaic.providerData["mosaic-provider-jobcards"]={"metaData":{"mosaicProviderJobCardsModel":{"results":[{"displayTitle":"Data Analyst Intern","company":"Acme Corp","formattedLocation":"Dallas, TX","jobkey":"abc123"},{"displayTitle":"BI Intern","company":"Widgets Inc","formattedLocation":"Remote","jobkey":"def456"}]}}};
</script>
</body></html>"""


def test_fetch_linkedin_parses_fixture():
    postings = fetch_linkedin("Data Analyst Intern", "Dallas, TX", fetch=lambda url: LINKEDIN_FIXTURE)
    assert len(postings) == 3
    assert postings[0].title == "Data Analyst Intern"
    assert postings[0].company == "Acme Corp"
    assert postings[0].location == "Dallas, TX"
    assert postings[0].url == "https://www.linkedin.com/jobs/view/data-analyst-intern-at-acme-4437848829"
    assert postings[0].source == "linkedin"
    assert postings[2].location == "Remote"


def test_fetch_linkedin_missing_company_link_does_not_shift_later_cards():
    """Regression for Finding 2: a card whose company has no LinkedIn page
    (bare text instead of the <a> the company regex requires) must default
    that one card's company to "" without shifting any other card's fields
    out of alignment, unlike the old whole-page findall-then-zip approach."""
    postings = fetch_linkedin("Data Analyst Intern", "Dallas, TX", fetch=lambda url: LINKEDIN_FIXTURE)
    middle = postings[1]
    assert middle.title == "No Company Page Intern"
    assert middle.company == ""
    assert middle.location == "Austin, TX"
    last = postings[2]
    assert last.title == "BI Intern"
    assert last.company == "Widgets Inc"
    assert last.location == "Remote"
    assert last.url == "https://www.linkedin.com/jobs/view/bi-intern-at-widgets-4437848830"


def test_fetch_linkedin_returns_empty_on_fetch_failure():
    def boom(url):
        raise TimeoutError("blocked")
    assert fetch_linkedin("x", "y", fetch=boom) == []


def test_fetch_indeed_parses_fixture():
    postings = fetch_indeed("Data Analyst Intern", "Dallas, TX", fetch=lambda url: INDEED_FIXTURE)
    assert len(postings) == 2
    assert postings[0].title == "Data Analyst Intern"
    assert postings[0].company == "Acme Corp"
    assert postings[0].url == "https://www.indeed.com/viewjob?jk=abc123"
    assert postings[0].source == "indeed"
    assert postings[1].company == "Widgets Inc"


def test_fetch_indeed_returns_empty_when_marker_missing():
    assert fetch_indeed("x", "y", fetch=lambda url: "<html>no data here</html>") == []


def test_fetch_posting_text_strips_tags():
    html = "<html><body><h1>Data Analyst Intern</h1><p>Requires SQL and Python.</p></body></html>"
    text = fetch_posting_text("https://example.com/job/1", fetch=lambda url: html)
    assert "Data Analyst Intern" in text
    assert "Requires SQL and Python." in text
    assert "<h1>" not in text
