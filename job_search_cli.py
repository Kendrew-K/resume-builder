"""CLI for Fall 2026 internship discovery and fit ranking.
Usage: python job_search_cli.py scrape
       python job_search_cli.py rank
"""
import argparse
import json
import os
import pathlib

from job_search.geocode import is_within_range
from job_search.markdown_output import parse_internships_md, write_internships_md
from job_search.posting import Posting, dedupe_postings, today_iso
from job_search.rank import FIT_THRESHOLD, fit_score, passes_threshold
from job_search.ats import descriptions as ats_descriptions
from job_search.ats import fetch_ats
from job_search.sources import (
    fetch_github_internships,
    fetch_glassdoor,
    fetch_indeed,
    fetch_linkedin,
    fetch_posting_text,
    fetch_ziprecruiter,
)
from job_search.tracker import (
    TrackerRow,
    find_by_url,
    is_handled,
    read_tracker,
    upsert,
    write_tracker,
)

# Everything below is overridable by environment variable so the repo carries no
# personal search config. KEYWORDS/LOCATIONS take comma-separated lists.
KEYWORDS = [k.strip() for k in os.environ.get(
    "JOB_SEARCH_KEYWORDS",
    "Data Analyst Intern,Data Science Intern,BI Intern").split(",") if k.strip()]
LOCATIONS = [l.strip() for l in os.environ.get(
    "JOB_SEARCH_LOCATIONS", "Dallas, TX;Remote").split(";") if l.strip()]
TRACKER_PATH = os.environ.get("JOB_SEARCH_TRACKER", "job_search_tracker.csv")
OUTPUT_PATH = os.environ.get("JOB_SEARCH_OUTPUT", "internships.md")
EXPERIENCES_PATH = os.environ.get("JOB_SEARCH_PROFILE", "experiences.md")

TEXT_CACHE_PATH = "ats_text.json"

SOURCE_FNS = [
    # ats first: the company's own job board, so it carries a posting before
    # any aggregator re-lists it, and its URL is the real apply link. github
    # second for the same reason (direct ATS links, no aggregation lag), so
    # dedupe keeps those URLs when the same job later appears on a job board.
    ("ats", fetch_ats),
    ("github", fetch_github_internships),
    ("linkedin", fetch_linkedin),
    ("indeed", fetch_indeed),
    ("glassdoor", fetch_glassdoor),
    ("ziprecruiter", fetch_ziprecruiter),
]


def filter_and_write(postings, tracker_path, output_path,
                     within_range=is_within_range) -> list[Posting]:
    """Dedupe postings, drop already-handled ones (per tracker_path), drop
    those outside the configured radius/remote filter, write the survivors
    to output_path and return them. Earlier postings win ties in dedupe, so
    callers should pass their most-trusted source first.
    """
    deduped = dedupe_postings(postings)
    tracker = read_tracker(tracker_path)
    fresh = [p for p in deduped if not is_handled(tracker, p.title, p.company, p.location)]
    nearby = [p for p in fresh if within_range(p.location)]
    write_internships_md(output_path, nearby)
    return nearby


def run_scrape(source_fns, keywords, locations, tracker_path, output_path,
                within_range=is_within_range) -> tuple[list[Posting], list[str]]:
    """Query every (source, keyword, location) combination, then filter and
    write the results. Returns the surviving postings alongside the names of
    sources that returned no results (blocked or genuinely empty) for any query.
    """
    all_postings: list[Posting] = []
    blocked: list[str] = []
    for kw in keywords:
        for loc in locations:
            for name, fn in source_fns:
                results = fn(kw, loc)
                if not results:
                    blocked.append(name)
                all_postings.extend(results)
    return filter_and_write(all_postings, tracker_path, output_path, within_range), sorted(set(blocked))


def run_ingest(json_path, tracker_path, output_path,
               within_range=is_within_range) -> tuple[list[Posting], int]:
    """Merge browser-collected postings into output_path.

    LinkedIn/Indeed/Glassdoor serve bot-walled or logged-out markup to the
    plain-HTTP fetchers in job_search.sources, so those postings are instead
    collected by Claude in Chrome driving the user's own logged-in browser and
    dumped to json_path as records of {title, company, location, url, source}.
    Existing rows in output_path are merged first so a previous `scrape` run's
    direct-ATS github URLs win dedupe over a job-board rewrite of the same job.
    Returns the surviving postings and how many of them came from json_path.
    """
    records = json.loads(pathlib.Path(json_path).read_text(encoding="utf-8"))
    from_chrome = [
        Posting(
            title=r["title"].strip(), company=r.get("company", "").strip(),
            location=r.get("location", "").strip(), url=r["url"].strip(),
            source=r.get("source", "chrome"), fetched_date=today_iso(),
        )
        for r in records if r.get("title") and r.get("url")
    ]
    existing = parse_internships_md(output_path) if pathlib.Path(output_path).exists() else []
    kept = filter_and_write(existing + from_chrome, tracker_path, output_path, within_range)
    return kept, len(from_chrome)


def run_rank(output_path, experiences_path,
             fetch_text=fetch_posting_text) -> tuple[list[Posting], int]:
    """Load previously-scraped postings from output_path, fetch each
    posting's full text and score it against the profile in
    experiences_path, rewrite output_path with scores filled in, and
    return the postings plus a count of those meeting FIT_THRESHOLD.
    """
    postings = parse_internships_md(output_path)
    profile_text = pathlib.Path(experiences_path).read_text(encoding="utf-8")
    for p in postings:
        posting_text = fetch_text(p.url)
        p.fit_score = fit_score(posting_text, profile_text)
    write_internships_md(output_path, postings)
    qualifying = sum(1 for p in postings if passes_threshold(p.fit_score))
    return postings, qualifying


def run_applied(output_path, tracker_path, urls) -> list[str]:
    """Mark the postings at `urls` as applied in the tracker.

    Tracker rows key on (title, company, location), and `filter_and_write`
    drops anything already applied/skipped, so a posting marked here never
    resurfaces in a later scrape — even when a different source surfaces it
    under a different URL. Returns the URLs that matched nothing.
    """
    postings = {p.url: p for p in parse_internships_md(output_path)}
    rows = read_tracker(tracker_path)
    missing = []
    for url in urls:
        posting = postings.get(url)
        if posting is not None:
            row = TrackerRow(
                company=posting.company, title=posting.title, location=posting.location,
                url=posting.url, status="applied",
                fit_score=f"{posting.fit_score:.2f}" if posting.fit_score is not None else "",
                date=today_iso(),
            )
        else:
            # Already worked once (pending-review/needs-manual), so filter_and_write
            # has dropped it from the markdown — the tracker row is the only record left.
            existing = find_by_url(rows, url)
            if existing is None:
                missing.append(url)
                continue
            row = TrackerRow(
                company=existing.company, title=existing.title, location=existing.location,
                url=existing.url, status="applied", fit_score=existing.fit_score,
                date=today_iso(),
            )
        upsert(rows, row)
    write_tracker(tracker_path, rows)
    return missing


def run_status(tracker_path) -> dict[str, list[TrackerRow]]:
    """Group every tracker row by status so the user can see what has been
    applied to, what is still sitting at a review screen, and what needs a
    manual application.
    """
    grouped: dict[str, list[TrackerRow]] = {}
    for row in read_tracker(tracker_path).values():
        grouped.setdefault(row.status, []).append(row)
    return grouped


def cached_posting_text(cache_path, fetch_text=fetch_posting_text):
    """Return a fetch_text-shaped callable that prefers browser-collected text.

    Indeed serves its job descriptions client-side and rate-limits (HTTP 429)
    plain-HTTP reads, so `fetch_posting_text` returns "" for those URLs and
    every Indeed posting scores 0. Claude in Chrome collects the descriptions
    it can into a {url: text} JSON cache; this falls back to HTTP for any URL
    the cache is missing, so a partial cache still improves the ranking.
    """
    cache = json.loads(pathlib.Path(cache_path).read_text(encoding="utf-8"))
    return lambda url: cache.get(url) or fetch_text(url)


def main():
    """Entry point: dispatches to run_scrape or run_rank based on the
    `scrape`/`rank` subcommand, using the module-level defaults above.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("scrape")
    rank = sub.add_parser("rank")
    rank.add_argument("--text-cache", help="JSON {url: description} collected by Claude in Chrome")
    ingest = sub.add_parser("ingest")
    ingest.add_argument("json_path", help="JSON dump collected by Claude in Chrome")
    sub.add_parser("status")
    applied = sub.add_parser("applied")
    applied.add_argument("urls", nargs="+", help="posting URLs to mark applied")
    args = parser.parse_args()

    if args.command == "scrape":
        postings, blocked = run_scrape(SOURCE_FNS, KEYWORDS, LOCATIONS, TRACKER_PATH, OUTPUT_PATH)
        # The ATS boards return descriptions for free; cache them so `rank`
        # never re-fetches those postings over HTTP.
        text = ats_descriptions()
        pathlib.Path(TEXT_CACHE_PATH).write_text(json.dumps(text), encoding="utf-8")
        print(f"Scraped {len(postings)} postings within range. Blocked/empty sources: {blocked}")
        print(f"Cached {len(text)} ATS descriptions to {TEXT_CACHE_PATH}")
    elif args.command == "applied":
        missing = run_applied(OUTPUT_PATH, TRACKER_PATH, args.urls)
        print(f"Marked {len(args.urls) - len(missing)} applied. Not found: {missing}")
    elif args.command == "status":
        grouped = run_status(TRACKER_PATH)
        for status in sorted(grouped):
            print()
            print(f"{status} ({len(grouped[status])})")
            for row in grouped[status]:
                print(f"  {row.date}  {row.company} - {row.title} ({row.location})")
    elif args.command == "ingest":
        postings, n = run_ingest(args.json_path, TRACKER_PATH, OUTPUT_PATH)
        print(f"Ingested {n} browser-collected postings. {len(postings)} total within range.")
    elif args.command == "rank":
        fetch_text = cached_posting_text(args.text_cache) if args.text_cache else fetch_posting_text
        postings, qualifying = run_rank(OUTPUT_PATH, EXPERIENCES_PATH, fetch_text=fetch_text)
        pct = int(FIT_THRESHOLD * 100)
        print(f"Ranked {len(postings)} postings. {qualifying} at or above {pct}% fit.")


if __name__ == "__main__":
    main()
