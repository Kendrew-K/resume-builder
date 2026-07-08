import datetime
from dataclasses import dataclass


@dataclass
class Posting:
    title: str
    company: str
    location: str
    url: str
    source: str
    fetched_date: str
    fit_score: float | None = None
    rationale: str | None = None


def today_iso() -> str:
    return datetime.date.today().isoformat()


def posting_key(title: str, company: str, location: str) -> tuple[str, str, str]:
    """Normalize (title, company, location) into the identity key used both to
    dedupe postings across sources and to key the applicant tracker, so a
    posting seen under different URLs (e.g. the same job on LinkedIn and
    Indeed) resolves to the same tracker row instead of re-entering as new.
    """
    return (title.strip().lower(), company.strip().lower(), location.strip().lower())


def dedupe_postings(postings: list[Posting]) -> list[Posting]:
    seen: dict[tuple[str, str, str], Posting] = {}
    for p in postings:
        key = posting_key(p.title, p.company, p.location)
        if key not in seen:
            seen[key] = p
    return list(seen.values())
