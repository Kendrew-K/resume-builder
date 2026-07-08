import json
import math
import time
import urllib.parse
import urllib.request

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
USER_AGENT = "job-search-script/1.0 (personal use, <EMAIL>)"
HOME_ADDRESS = "<HOME_ADDRESS>"
RADIUS_MILES = 20.0

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


def is_within_range(location: str, fetch=None) -> bool:
    if "remote" in location.lower():
        return True
    home = geocode(HOME_ADDRESS, fetch=fetch)
    target = geocode(location, fetch=fetch)
    if home is None or target is None:
        return False
    return haversine_miles(home, target) <= RADIUS_MILES
