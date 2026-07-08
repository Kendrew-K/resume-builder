"""CLI for Fall 2026 internship discovery and fit ranking.
Usage: python job_search_cli.py scrape
       python job_search_cli.py rank
"""
import argparse
import pathlib

from job_search.geocode import is_within_range
from job_search.markdown_output import parse_internships_md, write_internships_md
from job_search.posting import Posting, dedupe_postings
from job_search.rank import FIT_THRESHOLD, fit_score, passes_threshold
from job_search.sources import (
    fetch_glassdoor,
    fetch_indeed,
    fetch_linkedin,
    fetch_posting_text,
    fetch_ziprecruiter,
)
from job_search.tracker import is_handled, read_tracker

KEYWORDS = ["Data Analyst Intern", "Data Science Intern", "BI Intern"]
LOCATIONS = ["Dallas, TX", "Remote"]
TRACKER_PATH = "job_search_tracker.csv"
OUTPUT_PATH = "fall_2026_internships.md"
EXPERIENCES_PATH = "experiences.md"

SOURCE_FNS = [
    ("linkedin", fetch_linkedin),
    ("indeed", fetch_indeed),
    ("glassdoor", fetch_glassdoor),
    ("ziprecruiter", fetch_ziprecruiter),
]


def run_scrape(source_fns, keywords, locations, tracker_path, output_path,
                within_range=is_within_range) -> tuple[list[Posting], list[str]]:
    """Query every (source, keyword, location) combination, then dedupe,
    drop already-handled postings (per tracker_path), and drop postings
    outside the configured radius/remote filter. Writes survivors to
    output_path and returns them alongside the names of sources that
    returned no results (blocked or genuinely empty) for any query.
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
    deduped = dedupe_postings(all_postings)
    tracker = read_tracker(tracker_path)
    fresh = [p for p in deduped if not is_handled(tracker, p.url)]
    nearby = [p for p in fresh if within_range(p.location)]
    write_internships_md(output_path, nearby)
    return nearby, sorted(set(blocked))


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


def main():
    """Entry point: dispatches to run_scrape or run_rank based on the
    `scrape`/`rank` subcommand, using the module-level defaults above.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("scrape")
    sub.add_parser("rank")
    args = parser.parse_args()

    if args.command == "scrape":
        postings, blocked = run_scrape(SOURCE_FNS, KEYWORDS, LOCATIONS, TRACKER_PATH, OUTPUT_PATH)
        print(f"Scraped {len(postings)} postings within range. Blocked/empty sources: {blocked}")
    elif args.command == "rank":
        postings, qualifying = run_rank(OUTPUT_PATH, EXPERIENCES_PATH)
        pct = int(FIT_THRESHOLD * 100)
        print(f"Ranked {len(postings)} postings. {qualifying} at or above {pct}% fit.")


if __name__ == "__main__":
    main()
