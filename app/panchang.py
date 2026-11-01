# -*- coding: utf-8 -*-
"""
Daily Panchangam (திருக்கணிதம்) on Swiss Ephemeris, Lahiri ayanamsa.

For a civil date at a place:
  Tamil year (60-year cycle), Tamil month (solar / Sun's sidereal sign) and day number,
  weekday, tithi / nakshatra / yoga / karana with END times (chain across the day),
  sunrise, sunset, Rahu Kalam, Yamagandam, Gulikai (classical 8-part day table).
Everything is computed; nothing is tabulated or guessed.
"""
from __future__ import annotations

import datetime as dt
from zoneinfo import ZoneInfo

import swisseph as swe

from . import engine as E
from . import tamil as T

TAMIL_MONTHS = ["சித்திரை", "வைகாசி", "ஆனி", "ஆடி", "ஆவணி", "புரட்டாசி",
                "ஐப்பசி", "கார்த்திகை", "மார்கழி", "தை", "மாசி", "பங்குனி"]
# 60-year cycle; index 0 = பிரபவ = Tamil year beginning April 1987 (14-04-1987)
TAMIL_YEARS = ["பிரபவ", "விபவ", "சுக்ல", "பிரமோதூத", "பிரஜோற்பத்தி", "ஆங்கீரச", "ஸ்ரீமுக", "பவ", "யுவ", "தாது",
               "ஈஸ்வர", "வெகுதானிய", "பிரமாதி", "விக்கிரம", "விஷு", "சித்திரபானு", "சுபானு", "தாரண", "பார்த்திப", "விய",
               "சர்வஜித்", "சர்வதாரி", "விரோதி", "விக்ருதி", "கர", "நந்தன", "விஜய", "ஜய", "மன்மத", "துன்முகி",
               "ஹேவிளம்பி", "விளம்பி", "விகாரி", "சார்வரி", "பிலவ", "சுபகிருது", "சோபகிருது", "குரோதி", "விசுவாவசு", "பராபவ",
               "பிலவங்க", "கீலக", "சௌமிய", "சாதாரண", "விரோதிகிருது", "பரிதாபி", "பிரமாதீச", "ஆனந்த", "ராட்சச", "நள",
               "பிங்கள", "காளயுக்தி", "சித்தார்த்தி", "ரௌத்திரி", "துன்மதி", "துந்துபி", "ருத்ரோத்காரி", "ரக்தாட்சி", "குரோதன", "அட்சய"]
# 1-indexed part of the 8-part day (sunrise→sunset), Monday=0 … Sunday=6
RAHU_PART = {0: 2, 1: 7, 2: 5, 3: 6, 4: 4, 5: 3, 6: 8}
YAMA_PART = {0: 4, 1: 3, 2: 2, 3: 1, 4: 7, 5: 6, 6: 5}
GULI_PART = {0: 6, 1: 5, 2: 4, 3: 3, 4: 2, 5: 1, 6: 7}
TITHI_FULL = ["பிரதமை", "துவிதியை", "திருதியை", "சதுர்த்தி", "பஞ்சமி", "சஷ்டி", "சப்தமி", "அஷ்டமி",
              "நவமி", "தசமி", "ஏகாதசி", "துவாதசி", "திரயோதசி", "சதுர்த்தசி"]
KARANA_MOV = ["பவம்", "பாலவம்", "கௌலவம்", "தைதிலம்", "கரஜம்", "வணிஜம்", "பத்ரை (விஷ்டி)"]

_FLAGS = E.EPH_FLAG | swe.FLG_SIDEREAL


# ----------------------------------------------------------------------------- astronomy helpers
def _sid(jd: float, body: int) -> float:
    return E.norm(swe.calc_ut(jd, body, _FLAGS)[0][0])


def _elong(jd: float) -> float:           # Moon − Sun, 0..360
    return E.norm(_sid(jd, swe.MOON) - _sid(jd, swe.SUN))


def _yoga_sum(jd: float) -> float:
    return E.norm(_sid(jd, swe.MOON) + _sid(jd, swe.SUN))


def _moon(jd: float) -> float:
    return _sid(jd, swe.MOON)


def _sun(jd: float) -> float:
    return _sid(jd, swe.SUN)


def _next_crossing(fn, jd0: float, step_deg: float, forward_hours: float = 60.0) -> float | None:
    """
    First instant after jd0 when fn(jd) crosses the next multiple of step_deg.
    fn is monotonically increasing modulo 360 (true for all four panchang quantities).
    """
    v0 = fn(jd0)
    target = (int(v0 / step_deg) + 1) * step_deg
    lo, hi = jd0, jd0 + forward_hours / 24.0
    # coarse scan for a bracket
    t, prev = lo, v0
    while t < hi:
        t2 = min(t + 1 / 24.0, hi)
        v = fn(t2)
        if v < prev:                       # wrapped 360→0
            v += 360.0
        if v >= target:
            lo, hi = t, t2
            break
        t, prev = t2, v
    else:
        return None
    for _ in range(40):                      # bisection to ~1 s
        mid = (lo + hi) / 2
        vm = fn(mid)
        if vm < v0 - 1:                      # wrapped
            vm += 360.0
        if vm >= target:
            hi = mid
        else:
            lo = mid
    return (lo + hi) / 2


def _prev_sun_ingress(jd0: float) -> float:
    """Instant (before jd0) when the sidereal Sun entered its current sign."""
    s0 = _sun(jd0)
    target = int(s0 / 30) * 30
    lo, hi = jd0 - 40, jd0                   # a sign takes ~30 days
    for _ in range(45):
        mid = (lo + hi) / 2
        if _sun(mid) >= target and _sun(mid) < target + 30:
            hi = mid
        else:
            lo = mid
    return hi


def _rise_set(jd_midnight_ut: float, lat: float, lon: float):
    geo = (lon, lat, 0)
    rise = swe.rise_trans(jd_midnight_ut, swe.SUN, swe.CALC_RISE, geo, flags=E.EPH_FLAG)[1][0]
    sett = swe.rise_trans(rise, swe.SUN, swe.CALC_SET, geo, flags=E.EPH_FLAG)[1][0]
    nxt = swe.rise_trans(sett, swe.SUN, swe.CALC_RISE, geo, flags=E.EPH_FLAG)[1][0]
    return rise, sett, nxt


# ----------------------------------------------------------------------------- formatting
def _to_local(jd: float, zone: ZoneInfo) -> dt.datetime:
    y, m, d, h = swe.revjul(jd)
    return (dt.datetime(y, m, d, tzinfo=dt.timezone.utc) + dt.timedelta(hours=h)).astimezone(zone)


def _hm(t: dt.datetime) -> str:
    return t.strftime("%H:%M")


def _hm_day(t: dt.datetime, day: dt.date) -> str:
    """'HH:MM' or 'HH:MM (+1)' when the instant is on the following civil day."""
    s = t.strftime("%H:%M")
    n = (t.date() - day).days
    return s if n == 0 else f"{s} (+{n})"


# ----------------------------------------------------------------------------- core
def compute_panchang(*, date: str, lat: float, lon: float, tz_id: str) -> dict:
    zone = ZoneInfo(tz_id)
    day = dt.date.fromisoformat(date)
    local_midnight = dt.datetime(day.year, day.month, day.day, tzinfo=zone)
    jd_mid = swe.julday(day.year, day.month, day.day, 0) - local_midnight.utcoffset().total_seconds() / 86400

    with E._LOCK:
        swe.set_sid_mode(swe.SIDM_LAHIRI, 0, 0)
        rise, sett, next_rise = _rise_set(jd_mid, lat, lon)
        ayan = swe.get_ayanamsa_ex_ut(rise, E.EPH_FLAG)[1]

        sunrise, sunset, nrise = _to_local(rise, zone), _to_local(sett, zone), _to_local(next_rise, zone)
        weekday = sunrise.weekday()

        # --- tithi / nakshatra / yoga / karana chains from sunrise to next sunrise
        def chain(fn, step, names):
            out, jd = [], rise
            while True:
                v = fn(jd)
                idx = int(v / step)
                end = _next_crossing(fn, jd, step)
                rec = names(idx)
                rec["end_time"] = _hm_day(_to_local(end, zone), day) if end else None
                rec["end_iso"] = _to_local(end, zone).isoformat() if end else None
                out.append(rec)
                if end is None or end >= next_rise or len(out) >= 3:
                    break
                jd = end + 1e-5
            return out

        def tithi_name(i):
            paksha = "சுக்ல பட்சம்" if i < 15 else "கிருஷ்ண பட்சம்"
            n = "பௌர்ணமி" if i == 14 else "அமாவாசை" if i == 29 else TITHI_FULL[i % 15]
            return {"index": i + 1, "paksha_ta": paksha, "name_ta": n}

        def nak_name(i):
            i = min(i, 26)
            return {"index": i + 1, "name_ta": T.NAKSHATRAS_TA[i], "lord_ta": T.PLANETS_TA[E.NAK_LORDS[i % 9]]}

        def yoga_name(i):
            i = min(i, 26)
            return {"index": i + 1, "name_ta": T.YOGAS_TA[i]}

        def karana_name(k):
            n = "கிம்ஸ்துக்னம்" if k == 0 else "சகுனி" if k == 57 else "சதுஷ்பாதம்" if k == 58 else "நாகவம்" if k == 59 else KARANA_MOV[(k - 1) % 7]
            return {"index": k + 1, "name_ta": n}

        tithis = chain(_elong, 12.0, tithi_name)
        naks = chain(_moon, 360 / 27, nak_name)
        yogas = chain(_yoga_sum, 360 / 27, yoga_name)
        karanas = chain(_elong, 6.0, karana_name)

        # --- Tamil solar month & day (month = Sun's sidereal sign; day 1 = ingress day if ingress before sunset, else next day)
        sun_sign = int(_sun(rise) / 30)
        ingress = _prev_sun_ingress(rise)
        ing_local = _to_local(ingress, zone)
        ing_day_rise, ing_day_set, _ = _rise_set(swe.julday(ing_local.year, ing_local.month, ing_local.day, 0)
                                               - local_midnight.utcoffset().total_seconds() / 86400, lat, lon)
        month_start = ing_local.date() if ingress < ing_day_set else ing_local.date() + dt.timedelta(days=1)
        tamil_day = (day - month_start).days + 1
        # Tamil year starts at the Aries ingress (சித்திரை 1, mid-April): months மார்கழி…பங்குனி in Jan–Apr belong to the previous year
        yr_anchor = day.year - 1 if (day.month <= 4 and sun_sign in (8, 9, 10, 11)) else day.year
        tamil_year = TAMIL_YEARS[(yr_anchor - 1987) % 60]

        # --- Rahu Kalam / Yamagandam / Gulikai (8 equal parts of the day)
        part = (sett - rise) / 8

        def window(p):
            a = _to_local(rise + (p - 1) * part, zone); b = _to_local(rise + p * part, zone)
            return {"start": _hm(a), "end": _hm(b)}

        # --- Moon sign at sunrise (for ராசி பலன் linkage)
        moon_sign = int(_moon(rise) / 30)

    return {
        "calculation": {"engine": E.ENGINE, "ephemeris_data": E.EPHEMERIS_DATA, "ayanamsa": "lahiri",
                        "ayanamsa_ta": T.AYANAMSA_TA["lahiri"], "ayanamsa_value_dms": E.dms(ayan), "zodiac": "sidereal",
                        "day_boundary": "sunrise", "sunrise_definition": "upper limb with refraction (Swiss Ephemeris default)",
                        "tamil_month_rule": "solar month = Sun's sidereal sign; day 1 = ingress day if the ingress precedes sunset, else the next day",
                        "calculation_version": E.CALC_VERSION},
        "place": {"latitude": lat, "longitude": lon, "tz_id": tz_id, "utc_offset": local_midnight.strftime("%z")[:3] + ":" + local_midnight.strftime("%z")[3:]},
        "date": date, "date_display": day.strftime("%d-%m-%Y"),
        "weekday_ta": T.WEEKDAYS_TA[weekday],
        "tamil_date": {"year_ta": tamil_year, "month_ta": TAMIL_MONTHS[sun_sign], "day": tamil_day,
                       "text_ta": f"{tamil_year} வருடம் {TAMIL_MONTHS[sun_sign]} {tamil_day}",
                       "sankranti_local": ing_local.isoformat()},
        "sunrise": _hm(sunrise), "sunset": _hm(sunset), "next_sunrise": _hm_day(nrise, day),
        "day_length_minutes": round((sett - rise) * 1440, 1),
        "tithi": tithis, "nakshatra": naks, "yoga": yogas, "karana": karanas,
        "rahu_kalam": window(RAHU_PART[weekday]), "yamagandam": window(YAMA_PART[weekday]), "gulikai": window(GULI_PART[weekday]),
        "moon_sign_index": moon_sign, "moon_sign_ta": T.SIGNS_TA[moon_sign],
        "disclaimer_ta": "கணக்கீடு: திருக்கணிதம் (Swiss Ephemeris, லஹிரி அயனாம்சம்). உள்ளூர் பஞ்சாங்கங்களுடன் சில நிமிட வேறுபாடு இருக்கலாம்.",
    }
