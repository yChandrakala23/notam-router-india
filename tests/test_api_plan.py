"""POST /plan HTTP layer (database mocked).  Skipped without FastAPI."""

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx")
from fastapi.testclient import TestClient  # noqa: E402

import routing.planner as planner  # noqa: E402
from api.main import app  # noqa: E402
from api.relevance import RetrievalError, UnknownAirport  # noqa: E402
from tests.routing_helpers import feat  # noqa: E402


class _Conn:
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class _Engine:
    def begin(self):
        return _Conn()


BODY = {"src": "VIDP", "dst": "VABB", "etd": "2026-11-05T06:00:00Z", "fl": 200}


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr("api.db.get_engine", lambda: _Engine())
    return TestClient(app)


def test_plan_ok_with_seed_notams(client, monkeypatch):
    real = planner.plan_route

    def fake(src, dst, etd, fl, **kw):
        kw.pop("connection", None)
        kw.pop("persist", None)
        return real(src, dst, etd, fl, notam_features=[feat()], **kw)

    monkeypatch.setattr(planner, "plan_route", fake)
    r = client.post("/plan", json=BODY)
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "OK" and body["rejected_routes"] and body["best_route"]["geometry"]["type"] == "LineString"


@pytest.mark.parametrize("exc,code", [(RetrievalError("bad"), 422), (UnknownAirport("VOZZ"), 404),
                                      (RuntimeError("no db"), 503)])
def test_plan_errors(client, monkeypatch, exc, code):
    def boom(*a, **k):
        raise exc
    monkeypatch.setattr(planner, "plan_route", boom)
    assert client.post("/plan", json=BODY).status_code == code


def test_plan_validation(client):
    assert client.post("/plan", json={**BODY, "fl": 0}).status_code == 422
    assert client.post("/plan", json={"src": "VIDP"}).status_code == 422
