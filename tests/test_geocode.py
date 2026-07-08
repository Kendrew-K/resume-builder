import math
from job_search import geocode as geo


def test_haversine_known_distance():
    # 1 degree of longitude at the equator is ~69.17 miles
    dist = geo.haversine_miles((0.0, 0.0), (0.0, 1.0))
    assert math.isclose(dist, 69.17, rel_tol=0.01)


def test_geocode_parses_nominatim_response():
    geo._geocode_cache.clear()
    canned = '[{"lat":"33.0074446","lon":"-96.7974326"}]'
    result = geo.geocode("<HOME_ADDRESS>", fetch=lambda url: canned)
    assert result == (33.0074446, -96.7974326)


def test_geocode_returns_none_on_empty_results():
    geo._geocode_cache.clear()
    result = geo.geocode("nowhere real", fetch=lambda url: "[]")
    assert result is None


def test_is_within_range_true_for_remote_without_any_fetch():
    def boom(url):
        raise AssertionError("remote postings must never geocode")
    assert geo.is_within_range("Remote", fetch=boom) is True


def test_is_within_range_true_when_close():
    geo._geocode_cache.clear()
    home_json = '[{"lat":"33.0","lon":"-96.8"}]'
    near_json = '[{"lat":"33.05","lon":"-96.8"}]'  # ~3.5 miles north
    calls = {"n": 0}

    def fake_fetch(url):
        calls["n"] += 1
        return home_json if calls["n"] == 1 else near_json

    assert geo.is_within_range("Plano, TX", fetch=fake_fetch) is True


def test_is_within_range_false_when_far():
    geo._geocode_cache.clear()
    home_json = '[{"lat":"33.0","lon":"-96.8"}]'
    far_json = '[{"lat":"37.77","lon":"-122.42"}]'  # San Francisco, ~1500 miles
    calls = {"n": 0}

    def fake_fetch(url):
        calls["n"] += 1
        return home_json if calls["n"] == 1 else far_json

    assert geo.is_within_range("San Francisco, CA", fetch=fake_fetch) is False


def test_is_within_range_false_when_geocode_fails():
    geo._geocode_cache.clear()
    assert geo.is_within_range("Gibberish Place Name", fetch=lambda url: "[]") is False
