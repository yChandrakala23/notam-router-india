"""HTTP layer of GET /notams/relevant (database mocked).  Skipped without FastAPI."""

from datetime import datetime, timezone

import pytest

fastapi = pytest.importorskip("fastapi")
pytest.importorskip("httpx")
from fastapi.testclient import TestClient  # noqa: E402

import api.routers.notams as notams  # noqa: E402
from api.main import app  # noqa: E402
from api.relevance import RetrievalError, UnknownAirport, feature_collection  # noqa: E402


class _Conn:
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def execute(self, *a, **k):
        raise AssertionError("cache disabled in tests")


class _Engine:
    def connect(self):
        return _Conn()


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr("api.db.get_engine", lambda: _Engine())
    monkeypatch.setattr(notams.cache, "enabled", lambda: False)
    return TestClient(app)


def _fake(*args, **kwargs):
    feature = {"type": "Feature", "id": 1, "geometry": None, "properties": {
        "event_id": 1, "notam_id": "Z0001/26", "severity": "BLOCKING", "category": "AIRSPACE_RESTRICTION",
        "lower_fl": 0, "upper_fl": 250, "e_text": "SYNTHETIC",
        "valid_during": {"start": "2026-11-05T00:00:00Z", "end": None,
                         "end_estimated": False, "permanent": True}}}
    return feature_collection([feature], {"engine": "fake"})


def test_ok(client, monkeypatch):
    monkeypatch.setattr(notams, "relevant_notams", _fake)
    r = client.get("/notams/relevant", params={"src": "VIDP", "dst": "VABB",
                                               "etd": "2026-11-05T06:00:00Z", "fl_hi": 350})
    assert r.status_code == 200
    body = r.json()
    assert body["type"] == "FeatureCollection" and body["features"][0]["properties"]["severity"] == "BLOCKING"
    assert body["metadata"]["cache"] == "disabled"


def test_missing_required_params(client):
    assert client.get("/notams/relevant", params={"src": "VIDP"}).status_code == 422


def test_validation_error_maps_to_422(client, monkeypatch):
    def boom(*a, **k):
        raise RetrievalError("src must be an Indian ICAO aerodrome code")
    monkeypatch.setattr(notams, "relevant_notams", boom)
    r = client.get("/notams/relevant", params={"src": "KJFK", "dst": "VABB",
                                               "etd": "2026-11-05T06:00:00Z", "fl_hi": 350})
    assert r.status_code == 422


def test_unknown_airport_maps_to_404(client, monkeypatch):
    def boom(*a, **k):
        raise UnknownAirport("VOZZ")
    monkeypatch.setattr(notams, "relevant_notams", boom)
    r = client.get("/notams/relevant", params={"src": "VIDP", "dst": "VOZZ",
                                               "etd": "2026-11-05T06:00:00Z", "fl_hi": 350})
    assert r.status_code == 404


def test_database_down_maps_to_503(client, monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("DATABASE_URL is not configured")
    monkeypatch.setattr(notams, "relevant_notams", boom)
    r = client.get("/notams/relevant", params={"src": "VIDP", "dst": "VABB",
                                               "etd": "2026-11-05T06:00:00Z", "fl_hi": 350})
    assert r.status_code == 503 and "unavailable" in r.json()["detail"]
