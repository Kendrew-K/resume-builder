import json
import math
import os
import re
import time
import urllib.parse
import urllib.request

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
# Nominatim's usage policy requires a contact address in the User-Agent, so set
# JOB_SEARCH_CONTACT to your own email before running against the live service.
USER_AGENT = f"job-search-script/1.0 ({os.environ.get('JOB_SEARCH_CONTACT', 'set JOB_SEARCH_CONTACT')})"
HOME_ADDRESS = os.environ.get("JOB_SEARCH_HOME_ADDRESS", "Dallas, TX")
RADIUS_MILES = float(os.environ.get("JOB_SEARCH_RADIUS_MILES", "20"))

_geocode_cache: dict[str, tuple[float, float] | None] = {}


def _http_fetch(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=10) as resp:
        body = resp.read().decode("utf-8")
    time.sleep(1)  # Nominatim usage policy: max 1 request/second
    return body


def geocode(address: str, fetch=None) -> tuple[float, float] | None:
    if address in _geocode_cache:
        return _geocode_cache[address]
    fetch = fetch or _http_fetch
    params = urllib.parse.urlencode({"q": address, "format": "json", "limit": 1})
    try:
        body = fetch(f"{NOMINATIM_URL}?{params}")
        results = json.loads(body)
    except Exception:
        _geocode_cache[address] = None
        return None
    if not results:
        _geocode_cache[address] = None
        return None
    coord = (float(results[0]["lat"]), float(results[0]["lon"]))
    _geocode_cache[address] = coord
    return coord


def haversine_miles(a: tuple[float, float], b: tuple[float, float]) -> float:
    lat1, lon1 = a
    lat2, lon2 = b
    earth_radius_miles = 3958.8
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    h = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlambda / 2) ** 2
    return 2 * earth_radius_miles * math.asin(math.sqrt(h))


US_STATE_CODES = (
    "AL AK AZ AR CA CO CT DE FL GA HI ID IL IN IA KS KY LA ME MD MA MI MN MS MO "
    "MT NE NV NH NJ NM NY NC ND OH OK OR PA RI SC SD TN TX UT VT VA WA WV WI WY DC"
).split()

US_STATE_NAMES = [
    "alabama", "alaska", "arizona", "arkansas", "california", "colorado", "connecticut",
    "delaware", "florida", "georgia", "hawaii", "idaho", "illinois", "indiana", "iowa",
    "kansas", "kentucky", "louisiana", "maine", "maryland", "massachusetts", "michigan",
    "minnesota", "mississippi", "missouri", "montana", "nebraska", "nevada",
    "new hampshire", "new jersey", "new mexico", "new york", "north carolina",
    "north dakota", "ohio", "oklahoma", "oregon", "pennsylvania", "rhode island",
    "south carolina", "south dakota", "tennessee", "texas", "utah", "vermont",
    "virginia", "washington", "west virginia", "wisconsin", "wyoming",
]


def mentions_us(location: str) -> bool:
    """True if `location` names the US, a US state, or a `City, XX` state code.

    State codes are matched only against the original casing and only after a
    comma ("Dallas, TX"), because lowercased two-letter codes collide with
    ordinary words — IN/OR/ME/OK/HI/DE/LA/PA/CO all appear inside normal
    location text and would match almost anything.
    """
    low = location.lower()
    if re.search(r"\b(usa|u\.s\.a?\.?|united states)\b", low):
        return True
    if re.search(r",\s*(" + "|".join(US_STATE_CODES) + r")\b", location):
        return True
    return any(re.search(rf"\b{re.escape(name)}\b", low) for name in US_STATE_NAMES)


def is_within_range(location: str, fetch=None) -> bool:
    """True if the posting is commutable from HOME_ADDRESS or is US remote.

    A remote posting only counts if it is US-based. The job-board sources are
    global, so matching bare "remote" would admit "Colombia, Remote" and
    "Stuttgart (Remote)" — neither of which the user can take.
    """
    low = location.lower()
    if "remote" in low:
        elsewhere = re.sub(r"[^a-z]+", " ", low).replace("remote", " ").strip()
        # A location that says nothing but "remote" is taken at face value;
        # one that also names a place must name a US place.
        return not elsewhere or mentions_us(location)
    home = geocode(HOME_ADDRESS, fetch=fetch)
    target = geocode(location, fetch=fetch)
    if home is None or target is None:
        return False
    return haversine_miles(home, target) <= RADIUS_MILES
