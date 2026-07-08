import csv
import pathlib
from dataclasses import asdict, dataclass

TRACKER_FIELDS = ["company", "title", "url", "status", "fit_score", "date"]


@dataclass
class TrackerRow:
    company: str
    title: str
    url: str
    status: str  # pending | pending-review | applied | skipped | needs-manual
    fit_score: str
    date: str


def read_tracker(path) -> dict[str, TrackerRow]:
    path = pathlib.Path(path)
    if not path.exists():
        return {}
    rows: dict[str, TrackerRow] = {}
    with path.open(newline="", encoding="utf-8") as f:
        for raw in csv.DictReader(f):
            row = TrackerRow(**{k: raw[k] for k in TRACKER_FIELDS})
            rows[row.url] = row
    return rows


def write_tracker(path, rows: dict[str, TrackerRow]) -> None:
    path = pathlib.Path(path)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=TRACKER_FIELDS)
        writer.writeheader()
        for row in rows.values():
            writer.writerow(asdict(row))


def upsert(rows: dict[str, TrackerRow], row: TrackerRow) -> dict[str, TrackerRow]:
    rows[row.url] = row
    return rows


def is_handled(rows: dict[str, TrackerRow], url: str) -> bool:
    row = rows.get(url)
    return row is not None and row.status in ("applied", "skipped")
