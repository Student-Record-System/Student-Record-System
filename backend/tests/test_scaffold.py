from datetime import timedelta

from app.common.clock import Clock


def test_health_returns_ok(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.get_json() == {"status": "ok"}


def test_unknown_route_uses_standard_error_format(client):
    response = client.get("/api/does-not-exist")
    assert response.status_code == 404
    assert response.get_json()["error"]["code"] == "ERR_NOT_FOUND"


def test_clock_can_be_moved_forward():
    before = Clock.now()
    Clock.advance(minutes=16)
    assert Clock.now() - before >= timedelta(minutes=16)