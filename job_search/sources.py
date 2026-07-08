import json
import re
import urllib.parse
import urllib.request

from job_search.posting import Posting, today_iso

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
)


def _http_get(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=15) as resp:
        return resp.read().decode("utf-8", errors="ignore")


def _extract_json_object(text: str, start: int) -> str | None:
    depth = 0
    for j in range(start, len(text)):
        c = text[j]
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return text[start:j + 1]
    return None


def fetch_linkedin(keywords: str, location: str, fetch=None) -> list[Posting]:
    fetch = fetch or _http_get
    url = "https://www.linkedin.com/jobs/search?" + urllib.parse.urlencode(
        {"keywords": keywords, "location": location}
    )
    try:
        html = fetch(url)
    except Exception:
        return []
    titles = re.findall(r'base-search-card__title">\s*([^<]+?)\s*<', html)
    companies = re.findall(r'base-search-card__subtitle">\s*<a[^>]*>\s*([^<]+?)\s*<', html)
    locations = re.findall(r'job-search-card__location">\s*([^<]+?)\s*<', html)
    urls = re.findall(r'class="base-card__full-link[^"]*"\s+href="([^"?]+)', html)
    n = min(len(titles), len(companies), len(locations), len(urls))
    return [
        Posting(title=titles[i].strip(), company=companies[i].strip(),
                location=locations[i].strip(), url=urls[i].strip(),
                source="linkedin", fetched_date=today_iso())
        for i in range(n)
    ]


def fetch_indeed(keywords: str, location: str, fetch=None) -> list[Posting]:
    fetch = fetch or _http_get
    url = "https://www.indeed.com/jobs?" + urllib.parse.urlencode({"q": keywords, "l": location})
    try:
        html = fetch(url)
    except Exception:
        return []
    marker = 'window.mosaic.providerData["mosaic-provider-jobcards"]='
    idx = html.find(marker)
    if idx == -1:
        return []
    blob = _extract_json_object(html, idx + len(marker))
    if blob is None:
        return []
    try:
        data = json.loads(blob)
        results = data["metaData"]["mosaicProviderJobCardsModel"]["results"]
    except (KeyError, TypeError, json.JSONDecodeError):
        return []
    postings = []
    for r in results:
        title = r.get("displayTitle") or r.get("title")
        jobkey = r.get("jobkey")
        if not title or not jobkey:
            continue
        postings.append(Posting(
            title=title, company=r.get("company", ""),
            location=r.get("formattedLocation", ""),
            url=f"https://www.indeed.com/viewjob?jk={jobkey}",
            source="indeed", fetched_date=today_iso(),
        ))
    return postings


def fetch_posting_text(url: str, fetch=None) -> str:
    fetch = fetch or _http_get
    try:
        html = fetch(url)
    except Exception:
        return ""
    return re.sub(r"<[^>]+>", " ", html)


def fetch_glassdoor(keywords: str, location: str, fetch=None) -> list[Posting]:
    fetch = fetch or _http_get
    try:
        auto_url = "https://www.glassdoor.com/autocomplete/location?" + urllib.parse.urlencode(
            {"term": location, "locationTypeFilters": "CITY"}
        )
        candidates = json.loads(fetch(auto_url))
        if not candidates:
            return []
        loc_id = candidates[0]["locationId"]
        search_url = "https://www.glassdoor.com/Job/jobs.htm?" + urllib.parse.urlencode(
            {"sc.keyword": keywords, "locT": "C", "locId": loc_id}
        )
        html = fetch(search_url)
    except Exception:
        return []
    titles = re.findall(r'class="JobCard_jobTitle__[^"]*"[^>]*>([^<]+)<', html)
    hrefs = re.findall(r'class="JobCard_jobTitle__[^"]*"[^>]*href="([^"?]+)', html)
    companies = re.findall(r'class="EmployerProfile_compactEmployerName__[^"]*"[^>]*>([^<]+)<', html)
    locations = re.findall(r'class="JobCard_location__[^"]*"[^>]*>([^<]+)<', html)
    n = min(len(titles), len(hrefs), len(companies), len(locations))
    return [
        Posting(title=titles[i].strip(), company=companies[i].strip(),
                location=locations[i].strip(), url=hrefs[i].strip(),
                source="glassdoor", fetched_date=today_iso())
        for i in range(n)
    ]


def fetch_ziprecruiter(keywords: str, location: str, fetch=None) -> list[Posting]:
    # Confirmed blocked by a Cloudflare JS challenge during design research
    # (2026-07-08 live check) — this consistently degrades to an empty list
    # rather than raising, matching the graceful-degrade contract of every
    # other source. No attempt is made to bypass the challenge.
    fetch = fetch or _http_get
    url = "https://www.ziprecruiter.com/jobs-search?" + urllib.parse.urlencode(
        {"search": keywords, "location": location}
    )
    try:
        html = fetch(url)
    except Exception:
        return []
    if "Just a moment" in html or "cf-challenge" in html:
        return []
    return []
