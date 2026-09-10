"""Poll company ATS job boards directly, instead of via job aggregators.

Greenhouse, Lever and Ashby all expose a company's own board as public JSON
with no bot wall and no rate limit, so this reaches postings over plain HTTP
that LinkedIn/Indeed only serve to a logged-in browser (and that Indeed 429s
when asked for descriptions). It is also the freshest source: a company's own
board carries a posting before the aggregators re-list it.

None of the three offers a cross-company search, so the boards to poll have to
come from somewhere. They are derived from the SimplifyJobs GitHub listings
already fetched by job_search.sources: those entries link straight at company
ATS pages, so the board slugs can be read back out of their URLs and each
company polled directly from then on. No hand-maintained company list.
"""
import concurrent.futures
import functools
import html
import json
import re
import urllib.error
import urllib.request

from job_search.posting import Posting, today_iso
from job_search.sources import USER_AGENT, _github_listings_raw

# Board slug as it appears in a posting URL, e.g.
# https://job-boards.greenhouse.io/airbnb/jobs/123 -> ("greenhouse", "airbnb")
SLUG_PATTERNS = {
    "greenhouse": r"(?:job-boards|boards)\.greenhouse\.io/([^/?#]+)",
    "lever": r"jobs\.lever\.co/([^/?#]+)",
    "ashby": r"jobs\.ashbyhq\.com/([^/?#]+)",
}

BOARD_URLS = {
    "greenhouse": "https://boards-api.greenhouse.io/v1/boards/{slug}/jobs",
    "lever": "https://api.lever.co/v0/postings/{slug}?mode=json",
    "ashby": "https://api.ashbyhq.com/posting-api/job-board/{slug}",
}

# Every listing on these boards is a real job, not necessarily an internship,
# so titles are filtered down to internships the way the GitHub source's own
# term filter does.
INTERN_RE = re.compile(r"\bintern\b|\binternship\b|\bco-?op\b", re.I)

MAX_WORKERS = 8


def _get_json(url: str, timeout: int = 20):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8", errors="ignore"))


def _strip_html(raw: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html.unescape(raw or ""))).strip()


def board_slugs(listings_raw: str) -> dict[str, set[str]]:
    """Read {board: {slug}} out of the ATS URLs in the GitHub listings JSON."""
    try:
        listings = json.loads(listings_raw)
    except (json.JSONDecodeError, TypeError):
        return {}
    slugs: dict[str, set[str]] = {board: set() for board in SLUG_PATTERNS}
    for item in listings:
        url = item.get("url") or ""
        for board, pattern in SLUG_PATTERNS.items():
            match = re.search(pattern, url)
            if match:
                slugs[board].add(match.group(1).lower())
    return slugs


def _greenhouse(slug: str) -> list[tuple[Posting, str]]:
    data = _get_json(BOARD_URLS["greenhouse"].format(slug=slug))
    out = []
    for job in data.get("jobs", []):
        title = (job.get("title") or "").strip()
        url = (job.get("absolute_url") or "").strip()
        if not title or not url or not INTERN_RE.search(title):
            continue
        # The board listing omits the description; fetch it per matching job
        # rather than asking for ?content=true on every job on the board.
        text = ""
        try:
            detail = _get_json(f"{BOARD_URLS['greenhouse'].format(slug=slug)}/{job['id']}")
            text = _strip_html(detail.get("content", ""))
        except (urllib.error.URLError, OSError, json.JSONDecodeError, KeyError):
            pass  # a missing description only costs this posting its fit score
        out.append((Posting(
            title=title, company=(job.get("company_name") or slug).strip(),
            location=(job.get("location") or {}).get("name", "").strip(),
            url=url, source="greenhouse", fetched_date=today_iso(),
        ), text))
    return out


def _lever(slug: str) -> list[tuple[Posting, str]]:
    data = _get_json(BOARD_URLS["lever"].format(slug=slug))
    out = []
    for job in data:
        title = (job.get("text") or "").strip()
        url = (job.get("hostedUrl") or "").strip()
        if not title or not url or not INTERN_RE.search(title):
            continue
        categories = job.get("categories") or {}
        out.append((Posting(
            title=title, company=slug,
            location=(categories.get("location") or "").strip(),
            url=url, source="lever", fetched_date=today_iso(),
        ), _strip_html(job.get("descriptionPlain") or job.get("description", ""))))
    return out


def _ashby(slug: str) -> list[tuple[Posting, str]]:
    data = _get_json(BOARD_URLS["ashby"].format(slug=slug))
    out = []
    for job in data.get("jobs", []):
        title = (job.get("title") or "").strip()
        url = (job.get("jobUrl") or job.get("applyUrl") or "").strip()
        if not title or not url or not INTERN_RE.search(title):
            continue
        location = (job.get("location") or "").strip()
        if job.get("isRemote") and "remote" not in location.lower():
            location = f"{location} (Remote)".strip()
        out.append((Posting(
            title=title, company=slug, location=location,
            url=url, source="ashby", fetched_date=today_iso(),
        ), _strip_html(job.get("descriptionPlain") or job.get("descriptionHtml", ""))))
    return out


BOARD_FETCHERS = {"greenhouse": _greenhouse, "lever": _lever, "ashby": _ashby}


@functools.lru_cache(maxsize=1)
def _poll_all_boards() -> tuple[tuple[Posting, str], ...]:
    """Poll every derived board once per process and cache the result.

    The CLI calls this source once per (keyword, location) pair, and a full
    sweep is ~900 HTTP requests, so it must not repeat per query — same reason
    job_search.sources caches the GitHub listings download.
    """
    slugs = board_slugs(_github_listings_raw())
    jobs: list[tuple[str, str]] = [
        (board, slug) for board, board_slugs_ in slugs.items() for slug in sorted(board_slugs_)
    ]

    def poll(board_slug):
        board, slug = board_slug
        try:
            return BOARD_FETCHERS[board](slug)
        except (urllib.error.URLError, OSError, json.JSONDecodeError, TypeError, KeyError):
            # A company that has moved off this board 404s. Every other source
            # degrades to empty rather than raising; match that.
            return []

    results: list[tuple[Posting, str]] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        for found in pool.map(poll, jobs):
            results.extend(found)
    return tuple(results)


def fetch_ats(keywords: str, location: str, fetch=None) -> list[Posting]:
    """Internships across every derived company board matching `keywords`.

    `location` is ignored — each posting carries its own and the CLI's
    radius/remote filter runs downstream — matching fetch_github_internships.
    """
    tokens = [t for t in keywords.lower().split() if t not in ("intern", "internship")]
    return [
        posting for posting, _ in _poll_all_boards()
        if any(re.search(rf"\b{re.escape(t)}", posting.title.lower()) for t in tokens)
    ]


def descriptions() -> dict[str, str]:
    """{url: description} for everything the last board sweep returned, in the
    shape `job_search_cli.py rank --text-cache` consumes. The boards hand back
    descriptions for free, so ranking never needs to re-fetch these postings.
    """
    return {p.url: text for p, text in _poll_all_boards() if text}
