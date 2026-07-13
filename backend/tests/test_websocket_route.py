from fastapi.testclient import TestClient

from app.main import app


def test_websocket_accepts_and_reports_missing_job() -> None:
    client = TestClient(app)

    with client.websocket_connect("/api/screening/ws/missing-job") as websocket:
        payload = websocket.receive_json()

    assert payload["type"] == "error"
    assert "not found" in payload["message"].lower()
