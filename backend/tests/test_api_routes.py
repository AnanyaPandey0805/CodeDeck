from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_root_route_returns_service_info():
    response = client.get("/")
    assert response.status_code == 200
    body = response.json()
    assert body["service"] == "codedeck"
    assert body["docs"] == "/docs"
    assert body["health"] == "/health"


def test_favicon_route_is_no_content():
    response = client.get("/favicon.ico")
    assert response.status_code == 204
