# -*- coding: utf-8 -*-
import os, datetime as dt
os.environ["ADMIN_TOKEN"] = "t3st"
import pytest
from fastapi.testclient import TestClient
from app import panchang, palan
from app.main import app

c = TestClient(app)


def test_panchang_chennai_2026_11_01():
    p = panchang.compute_panchang(date="2026-11-01", lat=13.0827, lon=80.2707, tz_id="Asia/Kolkata")
    assert p["weekday_ta"] == "ஞாயிறு"
    assert p["tamil_date"]["month_ta"] == "ஐப்பசி" and p["tamil_date"]["year_ta"] == "பராபவ"
    assert p["sunrise"] == "06:02" and p["sunset"] == "17:42"
    assert p["rahu_kalam"] == {"start": "16:14", "end": "17:42"}        # Sunday = 8th part
    assert p["yamagandam"]["start"] == "11:52" and p["gulikai"]["start"] == "14:47"
    assert p["tithi"][0]["name_ta"].endswith("சப்தமி") and p["tithi"][0]["end_time"] == "14:52"
    assert p["nakshatra"][0]["name_ta"] == "பூசம்"
    assert p["moon_sign_ta"] == "கடகம்"


def test_panchang_deterministic_and_fast():
    a = panchang.compute_panchang(date="2025-04-14", lat=13.0827, lon=80.2707, tz_id="Asia/Kolkata")
    b = panchang.compute_panchang(date="2025-04-14", lat=13.0827, lon=80.2707, tz_id="Asia/Kolkata")
    assert a == b
    assert a["tamil_date"]["month_ta"] == "சித்திரை" and a["tamil_date"]["day"] == 1   # Tamil new year 2025
    assert a["tamil_date"]["year_ta"] == "விசுவாவசு"


def test_panchang_api_defaults_and_overrides():
    r = c.get("/api/v1/panchang"); assert r.status_code == 200
    j = r.json(); assert j["place"]["name_ta"] == "சென்னை" and j["date"] == j["today_chennai"]
    r = c.get("/api/v1/panchang?date=2026-11-01&latitude=51.5074&longitude=-0.1278&tz_id=Europe/London&place=லண்டன்")
    assert r.status_code == 200 and r.json()["place"]["utc_offset"] == "+00:00"
    assert c.get("/api/v1/panchang?date=2026-13-01").status_code == 422
    assert c.get("/api/v1/panchang?tz_id=Mars/Olympus").status_code == 422


def test_palan_rules_and_approval(tmp_path, monkeypatch):
    monkeypatch.setattr(palan, "DATA_DIR", str(tmp_path))
    d = palan.generate("2026-11-01")
    assert d["status"] == "draft" and len(d["readings"]) == 12
    moon = d["transits"]["Moon"]["sign_index"]
    for r in d["readings"]:
        assert r["houses"]["Moon"] == (moon - r["rasi_index"]) % 12 + 1
        assert 1 <= r["rating"] <= 5 and r["general_ta"] and r["work_ta"] and r["relationships_ta"]
        assert len(r["rules_fired"]) == 9
    chandrashtama = [r for r in d["readings"] if "chandrashtama" in r["flags"]]
    assert len(chandrashtama) == 1 and chandrashtama[0]["houses"]["Moon"] == 8
    # public endpoint hidden until approved
    assert c.get("/api/v1/rasi-palan?date=2026-11-01").status_code == 404
    assert c.get("/api/v1/admin/rasi-palan?date=2026-11-01").status_code == 401
    assert c.get("/api/v1/admin/rasi-palan?date=2026-11-01", headers={"x-admin-token": "wrong"}).status_code == 401
    r = c.post("/api/v1/admin/rasi-palan/approve", json={"date": "2026-11-01", "approver": "jothidar", "edits": {"3": {"general_ta": "திருத்தம்"}}},
               headers={"x-admin-token": "t3st"})
    assert r.status_code == 200 and r.json()["status"] == "approved"
    pub = c.get("/api/v1/rasi-palan?date=2026-11-01").json()
    assert pub["readings"][3]["general_ta"] == "திருத்தம்" and pub["readings"][3]["edited"] is True
    assert pub["disclaimer_ta"] and pub["label_ta"] == "பொதுவான ராசி பலன்"
    assert c.post("/api/v1/admin/rasi-palan/unpublish", json={"date": "2026-11-01"}, headers={"x-admin-token": "t3st"}).json()["status"] == "draft"
