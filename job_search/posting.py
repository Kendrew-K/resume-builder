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


def _dedupe_key(p: Posting) -> tuple[str, str, str]:
    return (p.title.strip().lower(), p.company.strip().lower(), p.location.strip().lower())


def dedupe_postings(postings: list[Posting]) -> list[Posting]:
    seen: dict[tuple[str, str, str], Posting] = {}
    for p in postings:
        key = _dedupe_key(p)
        if key not in seen:
            seen[key] = p
    return list(seen.values())
