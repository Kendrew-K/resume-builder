import csv
import pathlib
from dataclasses import asdict, dataclass

from job_search.posting import posting_key

TRACKER_FIELDS = ["company", "title", "location", "url", "status", "fit_score", "date"]


@dataclass
class TrackerRow:
    company: str
    title: str
    location: str
    url: str
    status: str  # pending | pending-review | applied | skipped | needs-manual
    fit_score: str
    date: str


def read_tracker(path) -> dict[tuple[str, str, str], TrackerRow]:
    """Load the tracker CSV keyed by posting_key(title, company, location) —
    the same identity key dedupe_postings uses — so a posting already marked
    applied/skipped is recognized even if a later scrape surfaces it under a
    different URL from another source.
    """
    path = pathlib.Path(path)
    if not path.exists():
        return {}
    rows: dict[tuple[str, str, str], TrackerRow] = {}
    with path.open(newline="", encoding="utf-8") as f:
        for raw in csv.DictReader(f):
            row = TrackerRow(**{k: raw[k] for k in TRACKER_FIELDS})
            rows[posting_key(row.title, row.company, row.location)] = row
    return rows


def write_tracker(path, rows: dict[tuple[str, str, str], TrackerRow]) -> None:
    path = pathlib.Path(path)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=TRACKER_FIELDS)
        writer.writeheader()
        for row in rows.values():
            writer.writerow(asdict(row))


def upsert(rows: dict[tuple[str, str, str], TrackerRow], row: TrackerRow) -> dict[tuple[str, str, str], TrackerRow]:
    rows[posting_key(row.title, row.company, row.location)] = row
    return rows


def is_handled(rows: dict[tuple[str, str, str], TrackerRow], title: str, company: str, location: str) -> bool:
    row = rows.get(posting_key(title, company, location))
    return row is not None and row.status in ("applied", "skipped")
