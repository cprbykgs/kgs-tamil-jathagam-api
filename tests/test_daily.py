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
    # public endpoint is open — no approval needed
    r = c.get("/api/v1/rasi-palan?date=2026-11-01"); assert r.status_code == 200 and r.json()["status"] == "published"
    assert c.get("/api/v1/admin/rasi-palan?date=2026-11-01").status_code == 401
    assert c.get("/api/v1/admin/rasi-palan?date=2026-11-01", headers={"x-admin-token": "wrong"}).status_code == 401
    r = c.post("/api/v1/admin/rasi-palan/approve", json={"date": "2026-11-01", "approver": "jothidar", "edits": {"3": {"general_ta": "திருத்தம்"}}},
               headers={"x-admin-token": "t3st"})
    assert r.status_code == 200 and r.json()["status"] == "approved"
    pub = c.get("/api/v1/rasi-palan?date=2026-11-01").json()
    assert pub["readings"][3]["general_ta"] == "திருத்தம்" and pub["readings"][3]["edited"] is True
    assert pub["disclaimer_ta"] and pub["label_ta"] == "பொதுவான ராசி பலன்"
    assert c.post("/api/v1/admin/rasi-palan/unpublish", json={"date": "2026-11-01"}, headers={"x-admin-token": "t3st"}).json()["status"] == "draft"


def test_panchang_extras_2026_11_02():
    p = panchang.compute_panchang(date="2026-11-02", lat=13.0827, lon=80.2707, tz_id="Asia/Kolkata")
    assert p["weekday_ta"] == "திங்கள்" and p["ayanam_ta"] == "தட்சிணாயணம்" and p["paksha_ta"] == "தேய்பிறை"
    assert p["tamil_date"]["text_ta"] == "பராபவ வருடம் ஐப்பசி 16"
    assert p["sentences_ta"]["tithi"] == "இன்று மதியம் 01.11 வரை அஷ்டமி, பின்பு நவமி"
    assert p["sentences_ta"]["nakshatra"].startswith("நாளை அதிகாலை 03.46 வரை ஆயில்யம், பின்பு மகம்")
    assert p["nokku_ta"] == "கீழ் நோக்கு நாள்" and p["day_nakshatra_ta"] == "ஆயில்யம்"
    assert p["soolam_ta"] == "கிழக்கு" and p["parigaram_ta"] == "தயிர்"
    assert p["nalla_neram"][0]["start"] == "06:15" and p["gowri_nalla_neram"][1]["start"] == "19:30"   # Monday table
    assert p["chandrashtamam"]["rasi_ta"] == "தனுசு" and p["chandrashtamam"]["items"][0]["name_ta"] == "பூராடம்"
    assert p["amirthathi_yogam"]["items"][0]["name_ta"] == "சித்த யோகம்" and p["amirthathi_yogam"]["items"][1]["name_ta"] == "மரண யோகம்"
    g = p["gochara"]["by_sign"]
    assert set(g[3]) == {"சந்", "செவ்"} and set(g[4]) == {"குரு", "கே"} and set(g[6]) == {"சூ", "புத", "சுக்"} and g[10] == ["ரா"] and g[11] == ["சனி"]
    assert p["lagna_at_sunrise"]["sign_ta"] == "துலாம்" and len(p["lagna_table"]) >= 12
    assert p["gochara"]["next_ingress"][0]["planet"] == "Moon"
