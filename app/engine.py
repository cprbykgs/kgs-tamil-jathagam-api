# -*- coding: utf-8 -*-
"""
Deterministic Vedic chart engine built directly on Swiss Ephemeris (pyswisseph).

Two presentation modes share one astronomical foundation:
  traditional : Lahiri ayanamsa, whole-sign Rasi houses, Vimshottari dasha
  kp          : Krishnamurti ayanamsa (Swiss Ephemeris SIDM_KRISHNAMURTI),
                Placidus cusps, star / sub / sub-sub lords, significators

Everything here is plain arithmetic on ephemeris output - no LLM involvement.
Swiss Ephemeris keeps global state (ephemeris path, sidereal mode), so every
calculation runs under one process-wide lock.
"""
from __future__ import annotations

import datetime as dt
import os
import threading
from zoneinfo import ZoneInfo

import swisseph as swe

from . import tamil as T

CALC_VERSION = "1.1.0"
ENGINE = f"Swiss Ephemeris {swe.version} via pyswisseph"
EPHE_DIR = os.environ.get("EPHE_DIR", os.path.join(os.path.dirname(__file__), "..", "ephe"))
DASHA_YEAR_DAYS = 365.25          # documented Vimshottari year length
_LOCK = threading.RLock()

if os.path.isdir(EPHE_DIR) and any(f.endswith(".se1") for f in os.listdir(EPHE_DIR)):
    swe.set_ephe_path(EPHE_DIR)
    EPH_FLAG = swe.FLG_SWIEPH
    EPHEMERIS_DATA = "Swiss Ephemeris .se1 files"
else:                               # fallback: built-in analytical model (arc-second level differences)
    EPH_FLAG = swe.FLG_MOSEPH
    EPHEMERIS_DATA = "Moshier analytical (no .se1 files found)"

AYANAMSAS = {"lahiri": swe.SIDM_LAHIRI, "krishnamurti": swe.SIDM_KRISHNAMURTI}
SWE_BODY = {"Sun": swe.SUN, "Moon": swe.MOON, "Mars": swe.MARS, "Mercury": swe.MERCURY,
            "Jupiter": swe.JUPITER, "Venus": swe.VENUS, "Saturn": swe.SATURN}
OWN = {"Sun": [4], "Moon": [3], "Mars": [0, 7], "Mercury": [2, 5], "Jupiter": [8, 11], "Venus": [1, 6], "Saturn": [9, 10]}
EXALT = {"Sun": 0, "Moon": 1, "Mars": 9, "Mercury": 5, "Jupiter": 3, "Venus": 11, "Saturn": 6}
NAK_SPAN = 360.0 / 27.0
NAK_LORDS = ["Ketu", "Venus", "Sun", "Moon", "Mars", "Rahu", "Jupiter", "Saturn", "Mercury"]  # Vimshottari order
DASHA_YEARS = {"Ketu": 7, "Venus": 20, "Sun": 6, "Moon": 10, "Mars": 7, "Rahu": 18, "Jupiter": 16, "Saturn": 19, "Mercury": 17}


# ----------------------------------------------------------------------------- helpers
def norm(x: float) -> float:
    return x % 360.0


def dms(x: float, with_sign: bool = False) -> str:
    """Round to whole arc-seconds *for display only*."""
    total = int(round(norm(x) * 3600))
    d, rem = divmod(total, 3600)
    m, s = divmod(rem, 60)
    if with_sign:
        return f"{d % 30:02d}°{m:02d}'{s:02d}\""
    return f"{d:03d}°{m:02d}'{s:02d}\""


def sign_index(lon: float) -> int:
    return int(norm(lon) // 30)


def nakshatra_of(lon: float) -> tuple[int, int]:
    """(nakshatra index 0-26, pada 1-4) from an unrounded longitude."""
    lon = norm(lon)
    idx = int(lon / NAK_SPAN)
    pada = int((lon - idx * NAK_SPAN) / (NAK_SPAN / 4)) + 1
    return min(idx, 26), min(pada, 4)


def sign_lord(sidx: int) -> str:
    return next(p for p, ss in OWN.items() if sidx in ss)


def dignity(planet: str, lon: float) -> str:
    if planet in ("Rahu", "Ketu"):
        return "neutral"
    s = sign_index(lon)
    if EXALT[planet] == s:
        return "exalted"
    if (EXALT[planet] + 6) % 12 == s:
        return "debilitated"
    if s in OWN[planet]:
        return "own"
    return "neutral"


def navamsa_lon(lon: float) -> float:
    lon = norm(lon)
    s = sign_index(lon)
    scaled = (lon - s * 30) * 9            # 0..270 : each navamsa = 30 units, avoids 30/9 float drift
    part = min(int(scaled // 30), 8)
    start = {0: 0, 1: 9, 2: 6, 3: 3}[s % 4]     # movable/fixed/dual/… start sign of the navamsa cycle
    return ((start + part) % 12) * 30 + (scaled - part * 30)


def kp_lords(lon: float) -> dict:
    """Vimshottari sub-division of the nakshatra: star lord, sub lord, sub-sub lord."""
    lon = norm(lon)
    nak_idx = int(lon / NAK_SPAN)
    star = NAK_LORDS[nak_idx % 9]
    pos = lon - nak_idx * NAK_SPAN                    # offset inside the nakshatra
    order = NAK_LORDS[NAK_LORDS.index(star):] + NAK_LORDS[:NAK_LORDS.index(star)]

    def subdivide(offset, span):
        t = 0.0
        for lord in order:
            L = span * DASHA_YEARS[lord] / 120.0
            if offset < t + L or lord == order[-1]:
                return lord, offset - t, L
            t += L
        return order[-1], offset, span            # unreachable, keeps type checkers calm

    sub, off2, L2 = subdivide(pos, NAK_SPAN)
    order_sub = NAK_LORDS[NAK_LORDS.index(sub):] + NAK_LORDS[:NAK_LORDS.index(sub)]
    t = 0.0
    subsub = order_sub[-1]
    for lord in order_sub:
        L = L2 * DASHA_YEARS[lord] / 120.0
        if off2 < t + L:
            subsub = lord
            break
        t += L
    return {"star_lord": star, "sub_lord": sub, "sub_sub_lord": subsub}


def ymd_diff(a: dt.datetime, b: dt.datetime) -> tuple[int, int, int]:
    y, m, d = b.year - a.year, b.month - a.month, b.day - a.day
    if d < 0:
        m -= 1
        prev = b.replace(day=1) - dt.timedelta(days=1)
        d += prev.day
    if m < 0:
        y -= 1
        m += 12
    return y, m, d


# ----------------------------------------------------------------------------- time handling
def resolve_birth_time(date_str: str, time_str: str, tz_id: str) -> dict:
    """
    Convert a civil birth time to UTC using the historical rules of the IANA zone
    for that specific date (never today's offset).  Seconds are preserved.
    """
    y, mo, d = (int(x) for x in date_str.split("-"))
    hh, mm, ss = (int(x) for x in (time_str.split(":") + ["0", "0"])[:3])
    zone = ZoneInfo(tz_id)
    local = dt.datetime(y, mo, d, hh, mm, ss, tzinfo=zone)
    # detect non-existent / ambiguous local times (DST gaps or folds)
    fold_alt = local.replace(fold=1)
    ambiguous = local.utcoffset() != fold_alt.utcoffset()
    nonexistent = local.astimezone(dt.timezone.utc).astimezone(zone).replace(tzinfo=None) != local.replace(tzinfo=None)
    utc = local.astimezone(dt.timezone.utc)
    off = local.utcoffset().total_seconds()
    sgn = "+" if off >= 0 else "-"
    offs = abs(int(off))
    return {
        "local": local, "utc": utc, "tz_id": tz_id,
        "utc_offset": f"{sgn}{offs // 3600:02d}:{(offs % 3600) // 60:02d}",
        "utc_offset_seconds": int(off),
        "ambiguous_local_time": ambiguous, "nonexistent_local_time": nonexistent,
        "jd_ut": swe.julday(utc.year, utc.month, utc.day,
                            utc.hour + utc.minute / 60 + utc.second / 3600 + utc.microsecond / 3.6e9),
    }


# ----------------------------------------------------------------------------- core
def _positions(jd: float, node: str) -> dict:
    flags = EPH_FLAG | swe.FLG_SPEED | swe.FLG_SIDEREAL
    out = {}
    for p, body in SWE_BODY.items():
        x = swe.calc_ut(jd, body, flags)[0]
        out[p] = {"lon": norm(x[0]), "speed": x[3], "retrograde": x[3] < 0}
    nid = swe.MEAN_NODE if node == "mean" else swe.TRUE_NODE
    x = swe.calc_ut(jd, nid, flags)[0]
    out["Rahu"] = {"lon": norm(x[0]), "speed": x[3], "retrograde": True}
    out["Ketu"] = {"lon": norm(x[0] + 180), "speed": x[3], "retrograde": True}
    return out


def _house_by_cusps(lon: float, cusps: list[float]) -> int:
    """Placidus house: the cusp interval that contains the longitude (1-12)."""
    for i in range(12):
        a, b = cusps[i], cusps[(i + 1) % 12]
        if (lon - a) % 360 < (b - a) % 360:
            return i + 1
    return 12


def _planet_record(name: str, lon: float, retro: bool, house: int, mode: str) -> dict:
    nk, pada = nakshatra_of(lon)
    s = sign_index(lon)
    rec = {
        "planet": name, "planet_ta": T.PLANETS_TA[name], "planet_ta_short": T.PLANETS_TA_SHORT[name],
        "longitude": lon, "longitude_dms": dms(lon),
        "sign_index": s, "sign": T.SIGNS_EN[s], "sign_ta": T.SIGNS_TA[s],
        "degree_in_sign": lon % 30, "degree_in_sign_dms": dms(lon, with_sign=True),
        "sign_lord": sign_lord(s), "sign_lord_ta": T.PLANETS_TA_SHORT[sign_lord(s)],
        "nakshatra_index": nk, "nakshatra": T.NAKSHATRAS_EN[nk], "nakshatra_ta": T.NAKSHATRAS_TA[nk],
        "pada": pada, "nakshatra_lord": NAK_LORDS[nk % 9], "nakshatra_lord_ta": T.PLANETS_TA_SHORT[NAK_LORDS[nk % 9]],
        "retrograde": retro, "house": house,
    }
    if name != "Ascendant":
        dg = dignity(name, lon)
        rec["dignity"] = dg
        rec["dignity_ta"] = T.DIGNITY_TA[dg]
    if mode == "kp":
        k = kp_lords(lon)
        rec.update({"star_lord": k["star_lord"], "sub_lord": k["sub_lord"], "sub_sub_lord": k["sub_sub_lord"],
                    "star_lord_ta": T.PLANETS_TA_SHORT[k["star_lord"]], "sub_lord_ta": T.PLANETS_TA_SHORT[k["sub_lord"]],
                    "sub_sub_lord_ta": T.PLANETS_TA_SHORT[k["sub_sub_lord"]]})
    return rec


def _vimshottari(moon_lon: float, birth_local: dt.datetime, as_of: dt.datetime) -> dict:
    """Three-level Vimshottari tree (maha → bhukti → antara) with 365.25-day years."""
    nk, _ = nakshatra_of(moon_lon)
    start_lord = NAK_LORDS[nk % 9]
    elapsed = (norm(moon_lon) - nk * NAK_SPAN) / NAK_SPAN
    balance_days = DASHA_YEARS[start_lord] * DASHA_YEAR_DAYS * (1 - elapsed)

    def ymd_from_days(days: float):
        y = int(days // DASHA_YEAR_DAYS)
        rem = days - y * DASHA_YEAR_DAYS
        m = int(rem // (DASHA_YEAR_DAYS / 12))
        d = int(rem - m * (DASHA_YEAR_DAYS / 12))
        return y, m, d

    def period(lord, start, length_days, level, parent_lord=None):
        end = start + dt.timedelta(days=length_days)
        rec = {"lord": lord, "lord_ta": T.PLANETS_TA[lord], "start": start.isoformat(), "end": end.isoformat(),
               "start_date": start.strftime("%d-%m-%Y"), "end_date": end.strftime("%d-%m-%Y"),
               "length_days": length_days, "current": start <= as_of < end}
        if level < 3:
            order = NAK_LORDS[NAK_LORDS.index(lord):] + NAK_LORDS[:NAK_LORDS.index(lord)]
            subs, t = [], start
            for sl in order:
                L = length_days * DASHA_YEARS[sl] / 120.0
                subs.append(period(sl, t, L, level + 1, lord))
                t += dt.timedelta(days=L)
            rec["sub_periods"] = subs
        return rec

    # The first (balance) maha dasha starts before birth; build its full span and keep only the part after birth.
    mahas = []
    i = NAK_LORDS.index(start_lord)
    full_start = birth_local - dt.timedelta(days=DASHA_YEARS[start_lord] * DASHA_YEAR_DAYS - balance_days)
    t = full_start
    for j in range(9):
        lord = NAK_LORDS[(i + j) % 9]
        L = DASHA_YEARS[lord] * DASHA_YEAR_DAYS
        rec = period(lord, t, L, 1)
        if j == 0:
            # trim sub-periods that ended before birth; mark the maha start as the birth moment
            rec["start"] = birth_local.isoformat(); rec["start_date"] = birth_local.strftime("%d-%m-%Y")
            rec["balance_at_birth"] = True
            rec["sub_periods"] = [s for s in rec["sub_periods"] if dt.datetime.fromisoformat(s["end"]) > birth_local]
            # the bhukti/antara running at birth start at the birth moment for display purposes
            for b in rec["sub_periods"][:1]:
                if dt.datetime.fromisoformat(b["start"]) < birth_local:
                    b["start"] = birth_local.isoformat(); b["start_date"] = birth_local.strftime("%d-%m-%Y"); b["balance_at_birth"] = True
                    b["sub_periods"] = [a for a in b["sub_periods"] if dt.datetime.fromisoformat(a["end"]) > birth_local]
                    for a in b["sub_periods"][:1]:
                        if dt.datetime.fromisoformat(a["start"]) < birth_local:
                            a["start"] = birth_local.isoformat(); a["start_date"] = birth_local.strftime("%d-%m-%Y"); a["balance_at_birth"] = True
        a1 = ymd_diff(birth_local, max(t, birth_local)); a2 = ymd_diff(birth_local, t + dt.timedelta(days=L))
        rec["age_start"] = {"y": a1[0], "m": a1[1], "d": a1[2]}
        rec["age_end"] = {"y": a2[0], "m": a2[1], "d": a2[2]}
        mahas.append(rec)
        t += dt.timedelta(days=L)

    cur = next((m for m in mahas if m["current"]), None)
    current = None
    if cur:
        bh = next((b for b in cur["sub_periods"] if b["current"]), None)
        an = next((a for a in bh["sub_periods"] if a["current"]), None) if bh else None
        current = {"maha": cur["lord"], "maha_ta": T.PLANETS_TA[cur["lord"]],
                   "bhukti": bh["lord"] if bh else None, "bhukti_ta": T.PLANETS_TA[bh["lord"]] if bh else None,
                   "antara": an["lord"] if an else None, "antara_ta": T.PLANETS_TA[an["lord"]] if an else None,
                   "maha_start": cur["start_date"], "maha_end": cur["end_date"],
                   "bhukti_start": bh["start_date"] if bh else None, "bhukti_end": bh["end_date"] if bh else None}
    by, bm, bd = ymd_from_days(balance_days)
    return {"system": "Vimshottari", "year_length_days": DASHA_YEAR_DAYS, "start_lord": start_lord,
            "start_lord_ta": T.PLANETS_TA[start_lord],
            "balance_at_birth": {"years": by, "months": bm, "days": bd, "total_days": balance_days,
                                 "text_ta": f"{T.PLANETS_TA[start_lord]} {by} வருடம் {bm} மாதம் {bd} நாள்"},
            "as_of": as_of.isoformat(), "current": current, "maha_dashas": mahas}


def _panchang(sun: float, moon: float, local: dt.datetime, lat: float, lon: float, jd_ut: float) -> dict:
    """Weekday (sunrise-based), tithi, karana, nitya yoga, Moon nakshatra."""
    elong = norm(moon - sun)
    tithi_n = int(elong / 12)
    paksha = "Shukla" if tithi_n < 15 else "Krishna"
    t_in = tithi_n % 15
    tithi_ta = "பௌர்ணமி" if tithi_n == 14 else "அமாவாசை" if tithi_n == 29 else T.TITHIS_TA[t_in]
    k = int(elong / 6)
    mov = ["Bava", "Balava", "Kaulava", "Taitila", "Garija", "Vanija", "Vishti"]
    karana = "Kimstughna" if k == 0 else "Shakuni" if k == 57 else "Chatushpada" if k == 58 else "Naga" if k == 59 else mov[(k - 1) % 7]
    yoga_i = int(norm(sun + moon) / NAK_SPAN)
    # Vedic weekday starts at sunrise: find the sunrise preceding the birth instant
    try:
        day0 = swe.julday(local.year, local.month, local.day, 0) - local.utcoffset().total_seconds() / 86400
        rise = swe.rise_trans(day0 - 1, swe.SUN, swe.CALC_RISE, (lon, lat, 0), flags=EPH_FLAG)[1][0]
        while True:
            nxt = swe.rise_trans(rise + 0.5, swe.SUN, swe.CALC_RISE, (lon, lat, 0), flags=EPH_FLAG)[1][0]
            if nxt > jd_ut:
                break
            rise = nxt
        y, m, d, h = swe.revjul(rise + local.utcoffset().total_seconds() / 86400)
        wd = dt.date(y, m, d).weekday()
        sunrise_local = (dt.datetime(y, m, d) + dt.timedelta(hours=h)).strftime("%H:%M:%S")
    except Exception:
        wd, sunrise_local = local.weekday(), None
    mn, mp = nakshatra_of(moon)
    return {"weekday_ta": T.WEEKDAYS_TA[wd], "sunrise_local": sunrise_local,
            "paksha": paksha, "paksha_ta": T.PAKSHA_TA[paksha], "tithi_number": tithi_n + 1, "tithi_ta": tithi_ta,
            "karana": karana, "karana_ta": T.KARANAS_TA[karana],
            "yoga": T.YOGAS_EN[yoga_i], "yoga_ta": T.YOGAS_TA[yoga_i],
            "moon_nakshatra_ta": T.NAKSHATRAS_TA[mn], "moon_pada": mp}


def compute_chart(*, name: str, date: str, time: str, tz_id: str, lat: float, lon: float,
                  mode: str = "traditional", node: str = "mean", as_of: str | None = None,
                  gender: str | None = None) -> dict:
    mode = "kp" if mode == "kp" else "traditional"
    ayan_key = "krishnamurti" if mode == "kp" else "lahiri"
    house_system = "placidus" if mode == "kp" else "whole_sign"
    bt = resolve_birth_time(date, time, tz_id)
    jd = bt["jd_ut"]
    local = bt["local"].replace(tzinfo=None)
    as_of_dt = dt.datetime.fromisoformat(as_of).replace(tzinfo=None) if as_of else dt.datetime.now(ZoneInfo(tz_id)).replace(tzinfo=None)

    with _LOCK:
        swe.set_sid_mode(AYANAMSAS[ayan_key], 0, 0)
        ayan_value = swe.get_ayanamsa_ex_ut(jd, EPH_FLAG)[1]
        pos = _positions(jd, node)
        hsys = b"P" if mode == "kp" else b"W"
        cusps, ascmc = swe.houses_ex(jd, lat, lon, hsys, swe.FLG_SIDEREAL)
        asc = norm(ascmc[0])
        cusps = [norm(c) for c in cusps[:12]]
        # transits (gochara) at as_of, same settings
        jd_now = swe.julday(as_of_dt.year, as_of_dt.month, as_of_dt.day,
                            as_of_dt.hour + as_of_dt.minute / 60) - bt["utc_offset_seconds"] / 86400
        transit = _positions(jd_now, node)

    lagna_sign = sign_index(asc)
    planets = []
    for p in T.PLANETS_EN:
        v = pos[p]
        h = (sign_index(v["lon"]) - lagna_sign) % 12 + 1 if mode == "traditional" else _house_by_cusps(v["lon"], cusps)
        planets.append(_planet_record(p, v["lon"], v["retrograde"], h, mode))
    asc_rec = _planet_record("Ascendant", asc, False, 1, mode)

    nav = [{"planet": p["planet"], "planet_ta_short": p["planet_ta_short"], "longitude": navamsa_lon(p["longitude"]),
            "sign_index": sign_index(navamsa_lon(p["longitude"])), "sign_ta": T.SIGNS_TA[sign_index(navamsa_lon(p["longitude"]))],
            "retrograde": p["retrograde"]} for p in planets]
    nav_asc = navamsa_lon(asc)

    result = {
        "calculation": {
            "engine": ENGINE, "ephemeris_data": EPHEMERIS_DATA, "calculation_version": CALC_VERSION,
            "mode": mode, "mode_ta": T.MODE_TA[mode],
            "ayanamsa": ayan_key, "ayanamsa_ta": T.AYANAMSA_TA[ayan_key],
            "ayanamsa_swe_id": int(AYANAMSAS[ayan_key]), "ayanamsa_value": ayan_value, "ayanamsa_value_dms": dms(ayan_value),
            "house_system": house_system, "house_system_ta": T.HOUSE_SYSTEM_TA[house_system],
            "node": node, "node_ta": "மத்திம ராகு (Mean Node)" if node == "mean" else "உண்மை ராகு (True Node)",
            "dasha_year_days": DASHA_YEAR_DAYS, "zodiac": "sidereal",
        },
        "birth": {
            "name": name, "gender": gender, "date": date, "time": time, "tz_id": tz_id,
            "utc_offset": bt["utc_offset"], "utc_datetime": bt["utc"].isoformat(), "julian_day_ut": jd,
            "latitude": lat, "longitude": lon,
            "ambiguous_local_time": bt["ambiguous_local_time"], "nonexistent_local_time": bt["nonexistent_local_time"],
            "age_as_of": dict(zip(("y", "m", "d"), ymd_diff(local, as_of_dt))),
        },
        "ascendant": asc_rec,
        "planets": planets,
        "navamsa": {"ascendant_sign_index": sign_index(nav_asc), "ascendant_sign_ta": T.SIGNS_TA[sign_index(nav_asc)],
                    "ascendant_longitude": nav_asc, "planets": nav},
        "transit": {"as_of": as_of_dt.isoformat(),
                    "planets": [{"planet": p, "planet_ta_short": T.PLANETS_TA_SHORT[p], "longitude": v["lon"],
                                 "sign_index": sign_index(v["lon"]), "sign_ta": T.SIGNS_TA[sign_index(v["lon"])],
                                 "retrograde": v["retrograde"]} for p, v in transit.items()]},
        "panchang": _panchang(pos["Sun"]["lon"], pos["Moon"]["lon"], bt["local"], lat, lon, jd),
        "dasha": _vimshottari(pos["Moon"]["lon"], local, as_of_dt),
    }
    if mode == "kp":
        cusp_recs = []
        for i, c in enumerate(cusps):
            r = _planet_record("Ascendant", c, False, i + 1, "kp")
            r.update({"planet": f"Cusp {i + 1}", "planet_ta": f"பாவகம் {i + 1}", "planet_ta_short": str(i + 1), "cusp": i + 1})
            r.pop("dignity", None); r.pop("dignity_ta", None)
            cusp_recs.append(r)
        # Significators — explicit KP ABCD rules
        occupants = {h: [p["planet"] for p in planets if p["house"] == h] for h in range(1, 13)}
        owners = {h: [cusp_recs[h - 1]["sign_lord"]] for h in range(1, 13)}
        star_of = {p["planet"]: p["star_lord"] for p in planets}
        house_of = {p["planet"]: p["house"] for p in planets}
        def houses_owned(pl): return [h for h in range(1, 13) if pl in owners[h]]
        planet_wise = {}
        for p in T.PLANETS_EN:
            sl = star_of[p]
            planet_wise[p] = {"A_star_lord_occupies": [house_of[sl]], "B_occupies": [house_of[p]],
                              "C_star_lord_owns": houses_owned(sl), "D_owns": houses_owned(p), "star_lord": sl}
        house_wise = {}
        for h in range(1, 13):
            own = owners[h]
            house_wise[h] = {"A_in_star_of_occupants": [p for p in T.PLANETS_EN if star_of[p] in occupants[h]],
                             "B_occupants": occupants[h],
                             "C_in_star_of_owner": [p for p in T.PLANETS_EN if star_of[p] in own],
                             "D_owner": own}
        result["kp"] = {"cusps": cusp_recs, "significators": {"planet_wise": planet_wise, "house_wise": house_wise},
                        "rule_note": "Planet: A=houses occupied by its star lord, B=houses it occupies, C=houses owned by its star lord, D=houses it owns. "
                                     "House: A=planets in the star of its occupants, B=occupants, C=planets in the star of its owner, D=owner (cusp sign lord). "
                                     "Rahu/Ketu are treated only by placement (no ownership); agent-of-dispositor rules are not applied in v1."}
    return result
