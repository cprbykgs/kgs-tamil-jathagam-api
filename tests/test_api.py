import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from fastapi.testclient import TestClient
from app.main import app
c = TestClient(app)

def test_health():
    r = c.get("/health"); assert r.status_code == 200 and r.json()["ok"]

def test_places_and_timezone():
    r = c.get("/api/v1/places", params={"q": "madurai"}); assert r.json()["results"][0]["name"] == "Madurai"
    r = c.get("/api/v1/timezone", params={"latitude": 13.08, "longitude": 80.27, "date": "1943-06-01"})
    assert r.json()["utc_offset"] == "+06:30"

def test_chart_endpoint_both_modes():
    body = {"name": "Koushik", "date": "2014-05-02", "time": "17:40:00", "tz_id": "Asia/Kolkata",
            "latitude": 13.0827, "longitude": 80.2707, "mode": "traditional", "as_of": "2026-11-01T12:00:00"}
    r = c.post("/api/v1/chart", json=body); assert r.status_code == 200
    assert r.json()["ascendant"]["longitude_dms"] == "188°19'44\""
    r = c.post("/api/v1/chart", json={**body, "mode": "kp"}); assert r.status_code == 200 and "kp" in r.json()

def test_validation_errors():
    r = c.post("/api/v1/chart", json={"date": "2014-5-2", "time": "17:40", "tz_id": "Asia/Kolkata", "latitude": 1, "longitude": 1})
    assert r.status_code == 422
    r = c.post("/api/v1/chart", json={"date": "2014-05-02", "time": "17:40:00", "tz_id": "Mars/Olympus", "latitude": 1, "longitude": 1})
    assert r.status_code == 422
