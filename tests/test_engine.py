# -*- coding: utf-8 -*-
"""
Validation suite. Reference values come from two independent sources:
  * the TP (Thangapandian) Tamil astrology app screenshot for Koushik, 02-05-2014 17:40 IST Chennai
    (Lahiri, mean node) — planets, lagna, nakshatra/pada, dasha dates
  * diliprk/VedicAstro (flatlib sidereal + pyswisseph) for KP star/sub/sub-sub lords and Placidus cusps
"""
import datetime as dt
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from app import engine, places

K = dict(name="Koushik", date="2014-05-02", time="17:40:00", tz_id="Asia/Kolkata", lat=13.0827, lon=80.2707)
AS_OF = "2026-11-01T12:00:00"

TP_REFERENCE = {  # absolute sidereal longitudes from the TP app
    "Ascendant": "188°19'44\"", "Sun": "017°57'28\"", "Moon": "056°38'47\"", "Mars": "166°59'26\"",
    "Mercury": "025°24'37\"", "Jupiter": "081°08'08\"", "Venus": "335°19'03\"", "Saturn": "206°34'36\"",
    "Rahu": "183°46'26\"", "Ketu": "003°46'26\"",
}
TP_NAK = {"Sun": ("பரணி", 2), "Moon": ("மிருகசீரிடம்", 1), "Mars": ("ஹஸ்தம்", 3), "Mercury": ("பரணி", 4),
          "Jupiter": ("புனர்பூசம்", 1), "Venus": ("உத்திரட்டாதி", 1), "Saturn": ("விசாகம்", 2),
          "Rahu": ("சித்திரை", 4), "Ketu": ("அஸ்வினி", 2), "Ascendant": ("சுவாதி", 1)}
TP_DASHA_ENDS = {"Mars": "06-08-2019", "Rahu": "05-08-2037", "Jupiter": "05-08-2053", "Saturn": "05-08-2072",
                 "Mercury": "05-08-2089", "Ketu": "05-08-2096", "Venus": "06-08-2116", "Sun": "06-08-2122", "Moon": "06-08-2132"}


def trad():
    return engine.compute_chart(**K, mode="traditional", as_of=AS_OF)


def test_planets_match_tp_reference():
    r = trad()
    assert r["ascendant"]["longitude_dms"] == TP_REFERENCE["Ascendant"]
    for p in r["planets"]:
        if p.get("is_upagraha"):
            continue
        assert p["longitude_dms"] == TP_REFERENCE[p["planet"]], p["planet"]
        assert (p["nakshatra_ta"], p["pada"]) == TP_NAK[p["planet"]], p["planet"]
    assert r["planets"][2]["retrograde"] and r["planets"][6]["retrograde"]     # Mars, Saturn retrograde that day


def test_settings_are_reported():
    c = trad()["calculation"]
    assert c["ayanamsa"] == "lahiri" and c["house_system"] == "whole_sign" and c["node"] == "mean"
    assert c["engine"].startswith("Swiss Ephemeris") and c["calculation_version"]
    assert abs(c["ayanamsa_value"] - 24.0593) < 0.001


def test_dasha_dates_and_balance_match_tp():
    d = trad()["dasha"]
    assert d["balance_at_birth"]["years"] == 5 and d["balance_at_birth"]["months"] == 3 and d["balance_at_birth"]["days"] == 3
    ends = {m["lord"]: m["end_date"] for m in d["maha_dashas"]}
    # TP rounds the balance boundary to the nearest day; the engine keeps exact instants, so allow ±1 day there.
    for lord, ref in TP_DASHA_ENDS.items():
        got = dt.datetime.strptime(ends[lord], "%d-%m-%Y"); exp = dt.datetime.strptime(ref, "%d-%m-%Y")
        assert abs((got - exp).days) <= 1, (lord, ends[lord], ref)
    cur = d["current"]
    assert (cur["maha"], cur["bhukti"], cur["antara"]) == ("Rahu", "Saturn", "Rahu")
    assert cur["bhukti_start"] == "10-09-2024" and cur["bhukti_end"] == "18-07-2027"


def test_dasha_tree_is_chronological_and_nested():
    d = trad()["dasha"]
    prev_end = None
    for m in d["maha_dashas"]:
        ms, me = dt.datetime.fromisoformat(m["start"]), dt.datetime.fromisoformat(m["end"])
        assert ms < me
        if prev_end: assert abs((ms - prev_end).total_seconds()) < 1
        prev_end = me
        for b in m["sub_periods"]:
            bs, be = dt.datetime.fromisoformat(b["start"]), dt.datetime.fromisoformat(b["end"])
            assert ms - dt.timedelta(seconds=1) <= bs < be <= me + dt.timedelta(seconds=1) or m.get("balance_at_birth")
            for a in b["sub_periods"]:
                as_, ae = dt.datetime.fromisoformat(a["start"]), dt.datetime.fromisoformat(a["end"])
                assert bs - dt.timedelta(seconds=1) <= as_ < ae <= be + dt.timedelta(seconds=1)
    assert sum(1 for m in d["maha_dashas"] if m["current"]) == 1


def test_panchang_matches_tp():
    p = trad()["panchang"]
    assert p["weekday_ta"] == "வெள்ளி" and p["tithi_ta"] == "சதுர்த்தி" and p["paksha"] == "Shukla"
    assert p["karana_ta"] == "வணிஜம்" and p["yoga_ta"] == "அதிகண்டம்"


def test_determinism():
    a, b = trad(), trad()
    assert a["planets"] == b["planets"] and a["dasha"] == b["dasha"]


def test_seconds_are_preserved():
    a = engine.compute_chart(**{**K, "time": "17:40:00"}, mode="traditional", as_of=AS_OF)
    b = engine.compute_chart(**{**K, "time": "17:40:30"}, mode="traditional", as_of=AS_OF)
    assert abs((b["birth"]["julian_day_ut"] - a["birth"]["julian_day_ut"]) * 86400 - 30) < 1e-3
    assert b["ascendant"]["longitude"] > a["ascendant"]["longitude"]


def test_historical_timezone_offsets():
    # India used +06:30 war time in 1942-45; the engine must use the rule for the birth date, not today's
    assert places.offset_on("Asia/Kolkata", "1943-06-01")["utc_offset"] == "+06:30"
    assert places.offset_on("Asia/Kolkata", "2014-05-02")["utc_offset"] == "+05:30"
    assert places.offset_on("America/New_York", "2020-07-04")["utc_offset"] == "-04:00"
    assert places.offset_on("America/New_York", "2020-01-04")["utc_offset"] == "-05:00"
    r = engine.compute_chart(**{**K, "date": "1943-06-01"}, mode="traditional", as_of=AS_OF)
    assert r["birth"]["utc_offset"] == "+06:30"


def test_midnight_and_overseas():
    r = engine.compute_chart(name="x", date="2000-01-01", time="00:00:00", tz_id="America/Los_Angeles",
                             lat=34.05, lon=-118.24, mode="traditional", as_of=AS_OF)
    assert r["birth"]["utc_datetime"].startswith("2000-01-01T08:00:00")
    assert 1 <= r["ascendant"]["house"] <= 12 and len(r["planets"]) == 10


def test_boundaries_sign_nakshatra_pada_navamsa():
    # exact boundaries must be assigned without rounding artefacts
    assert engine.sign_index(29.9999999) == 0 and engine.sign_index(30.0) == 1
    assert engine.nakshatra_of(13.3333333) == (0, 4) and engine.nakshatra_of(13.3333334) == (1, 1)
    assert engine.nakshatra_of(3.3333333) == (0, 1) and engine.nakshatra_of(3.3333334) == (0, 2)
    assert engine.sign_index(engine.navamsa_lon(3.3333333)) == 0 and engine.sign_index(engine.navamsa_lon(3.3333334)) == 1
    assert engine.sign_index(engine.navamsa_lon(30.0)) == 9      # Taurus 0° → Capricorn navamsa


def test_kp_uses_its_own_settings():
    t, k = trad(), engine.compute_chart(**K, mode="kp", as_of=AS_OF)
    assert k["calculation"]["ayanamsa"] == "krishnamurti" and k["calculation"]["house_system"] == "placidus"
    assert abs(k["calculation"]["ayanamsa_value"] - 23.9625) < 0.001
    assert k["planets"][0]["longitude"] != t["planets"][0]["longitude"]          # really recalculated
    assert len(k["kp"]["cusps"]) == 12 and all("sub_lord" in c for c in k["kp"]["cusps"])


def test_kp_against_vedicastro():
    try:
        from vedicastro.VedicAstro import VedicHoroscopeData
    except ImportError:
        import pytest; pytest.skip("VedicAstro not installed")
    k = engine.compute_chart(**K, mode="kp", as_of=AS_OF)
    h = VedicHoroscopeData(2014, 5, 2, 17, 40, 0, 13.0827, 80.2707, "Asia/Kolkata", "Krishnamurti", "Placidus")
    ch = h.generate_chart()
    vp = {p.Object: p for p in h.get_planets_data_from_chart(ch)}
    vh = {x.Object: x for x in h.get_houses_data_from_chart(ch)}
    for p in k["planets"]:
        if p.get("is_upagraha"):
            continue
        v = vp[p["planet"]]
        assert abs(p["longitude"] - v.LonDecDeg) < 0.002 and p["house"] == v.HouseNr
        assert (p["star_lord"], p["sub_lord"], p["sub_sub_lord"]) == (v.NakshatraLord, v.SubLord, v.SubSubLord)
    roman = ["I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X", "XI", "XII"]
    for c in k["kp"]["cusps"]:
        v = vh[roman[c["cusp"] - 1]]
        assert abs(c["longitude"] - v.LonDecDeg) < 0.002 and c["sub_lord"] == v.SubLord


def test_place_search():
    hits = places.search("chennai")
    assert hits and hits[0]["name"] == "Chennai" and hits[0]["tz_id"] == "Asia/Kolkata"
    assert places.search("சென்னை")[0]["name"] == "Chennai"
    assert places.timezone_for(13.08, 80.27) == "Asia/Kolkata"


def test_mandi_sivamayam_shortcut():
    """மாந்தி = naazhigai x 6 + Sun (+180 at night). Night birth on Vedic Sunday (before sunrise) -> 10 naazhigai.
    Reference: an independent Tamil astrology app shows மாந்தி 121°40'35" (மகம் 1) for this birth at 03:15."""
    r = engine.compute_chart(name="t", date="1995-12-18", time="03:15:00", tz_id="Asia/Kolkata", lat=8.7674, lon=78.1342)
    m = r["mandi"]
    assert m["longitude_dms"] == "121°40'35\"" and (m["nakshatra_ta"], m["pada"]) == ("மகம்", 1)
    assert m["mandi_birth_period"] == "night" and m["mandi_naazhigai"] == 10 and m["house"] == 11
    assert r["planets"][-1]["planet"] == "Mandi" and r["planets"][-1]["planet_ta_short"] == "மா"
    # day birth: Wednesday noon Chennai -> 14 naazhigai, Sun + 84
    d = engine.compute_chart(name="t", date="2026-11-11", time="12:00:00", tz_id="Asia/Kolkata", lat=13.08, lon=80.27)
    sun = next(p for p in d["planets"] if p["planet"] == "Sun")
    assert d["mandi"]["mandi_naazhigai"] == 14 and abs((d["mandi"]["longitude"] - sun["longitude"]) % 360 - 84) < 1e-9
