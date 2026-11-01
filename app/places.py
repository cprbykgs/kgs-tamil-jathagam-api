# -*- coding: utf-8 -*-
"""Offline place search (GeoNames cities ≥ 15k population, via geonamescache) + historical timezone resolution."""
from __future__ import annotations
import datetime as dt
from functools import lru_cache
from zoneinfo import ZoneInfo
import geonamescache
from timezonefinder import TimezoneFinder

_gc = geonamescache.GeonamesCache()
_tf = TimezoneFinder()
_COUNTRIES = {k: v["name"] for k, v in _gc.get_countries().items()}

@lru_cache(maxsize=1)
def _index():
    rows = []
    for c in _gc.get_cities().values():
        names = {c["name"].lower()} | {a.lower() for a in c.get("alternatenames", [])}
        rows.append((names, c))
    return rows

def search(q: str, limit: int = 10) -> list[dict]:
    q = q.strip().lower()
    if len(q) < 2:
        return []
    hits = []
    for names, c in _index():
        score = 0
        if c["name"].lower().startswith(q): score = 3
        elif any(n.startswith(q) for n in names): score = 2
        elif q in c["name"].lower(): score = 1
        if score:
            hits.append((score, c["population"], c))
    hits.sort(key=lambda x: (-x[0], -x[1]))
    return [{"geonameid": c["geonameid"], "name": c["name"], "admin1_code": c.get("admin1code"),
             "country_code": c["countrycode"], "country": _COUNTRIES.get(c["countrycode"], c["countrycode"]),
             "latitude": c["latitude"], "longitude": c["longitude"], "tz_id": c["timezone"]}
            for _, _, c in hits[:limit]]

def timezone_for(lat: float, lon: float) -> str | None:
    return _tf.timezone_at(lat=lat, lng=lon)

def offset_on(tz_id: str, date: str, time: str = "12:00:00") -> dict:
    y, m, d = (int(x) for x in date.split("-")); hh, mm, ss = (int(x) for x in (time.split(":") + ["0", "0"])[:3])
    z = ZoneInfo(tz_id)
    local = dt.datetime(y, m, d, hh, mm, ss, tzinfo=z)
    off = int(local.utcoffset().total_seconds()); sgn = "+" if off >= 0 else "-"
    return {"tz_id": tz_id, "utc_offset": f"{sgn}{abs(off)//3600:02d}:{(abs(off)%3600)//60:02d}", "utc_offset_seconds": off,
            "abbreviation": local.tzname()}
