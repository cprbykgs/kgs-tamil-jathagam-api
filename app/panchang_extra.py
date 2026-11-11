# -*- coding: utf-8 -*-
"""
Extra daily-calendar items in the style of printed Tamil daily calendars.

Computed from the ephemeris (nothing guessed):
  ayanam, paksha (வளர்பிறை/தேய்பிறை), நோக்கு நாள் (by the day's nakshatra), சந்திராஷ்டமம் (by nakshatra and by rasi),
  அமிர்தாதி யோகம் (weekday × nakshatra), lagna at sunrise with its remaining நாழிகை, the day's 12-lagna timetable,
  கோச்சாரம் (transit chart at sunrise) with the next sign-change date of each planet,
  and lay-man Tamil time sentences ("இன்று மாலை 01.11 வரை அஷ்டமி, பின்பு நவமி").

Taken from traditional fixed tables (sources are cited in README):
  நல்ல நேரம் and கௌரி நல்ல நேரம் (fixed clock-time table by weekday, as used in printed calendars),
  சூலம் / பரிகாரம் by weekday, அமிர்தாதி யோகம் table, நோக்கு nakshatra groups.

Deliberately NOT provided: நேத்திரம் / ஜீவன் — published sources disagree on the rule, so it is left out until a
verified rule is supplied.
"""
from __future__ import annotations

import datetime as dt
from zoneinfo import ZoneInfo

import swisseph as swe

from . import engine as E
from . import tamil as T

# ----------------------------------------------------------------------------- fixed tables (weekday: Monday=0 … Sunday=6)
# Printed-calendar convention (fixed clock times). Thursday has no evening நல்ல நேரம் in this table.
NALLA_NERAM = {
    0: [("06:15", "07:15"), ("16:45", "17:45")],
    1: [("07:45", "08:45"), ("16:45", "17:45")],
    2: [("09:15", "10:15"), ("16:45", "17:45")],
    3: [("10:45", "11:45")],
    4: [("09:15", "10:15"), ("16:45", "17:45")],
    5: [("07:45", "08:45"), ("16:45", "17:45")],
    6: [("07:45", "08:45"), ("15:15", "16:15")],
}
GOWRI_NERAM = {
    0: [("09:15", "10:15"), ("19:30", "20:30")],
    1: [("10:45", "11:45"), ("19:30", "20:30")],
    2: [("06:15", "07:15"), ("18:30", "19:30")],
    3: [("12:15", "13:15"), ("18:30", "19:30")],
    4: [("06:15", "07:15"), ("19:30", "20:30")],
    5: [("10:45", "11:45"), ("21:30", "22:30")],
    6: [("10:45", "11:45"), ("13:30", "14:30")],
}
SOOLAM = {0: "கிழக்கு", 1: "வடக்கு", 2: "வடக்கு", 3: "தெற்கு", 4: "மேற்கு", 5: "கிழக்கு", 6: "மேற்கு"}
PARIGARAM = {0: "தயிர்", 1: "பால்", 2: "பால்", 3: "எண்ணெய்", 4: "வெல்லம்", 5: "தயிர்", 6: "வெல்லம்"}

# நோக்கு by nakshatra (0-based indices into T.NAKSHATRAS_TA)
MEL_NOKKU = {3, 5, 7, 11, 20, 21, 22, 23, 25}          # ரோகிணி திருவாதிரை பூசம் உத்திரம் உத்திராடம் திருவோணம் அவிட்டம் சதயம் உத்திரட்டாதி
KEEL_NOKKU = {1, 2, 8, 9, 10, 15, 18, 19, 24}          # பரணி கிருத்திகை ஆயில்யம் மகம் பூரம் விசாகம் மூலம் பூராடம் பூரட்டாதி
# everything else = சமநோக்கு (அஸ்வினி மிருகசீரிடம் புனர்பூசம் ஹஸ்தம் சித்திரை சுவாதி அனுஷம் கேட்டை ரேவதி)

# அமிர்தாதி யோகம்: weekday → {nakshatra index: yogam}. Nakshatras not listed under அமிர்த/மரண are சித்த யோகம்,
# except the one பிரபலாரிஷ்ட star per weekday.
_N = {n: i for i, n in enumerate(T.NAKSHATRAS_TA)}
_AMIRTHA = {
    6: ["உத்திரம்", "மூலம்", "உத்திராடம்", "திருவோணம்", "உத்திரட்டாதி", "ரேவதி"],
    0: ["ரோகிணி", "புனர்பூசம்", "சுவாதி", "திருவோணம்"],
    1: ["ரோகிணி", "உத்திரம்", "மூலம்", "உத்திரட்டாதி"],
    2: ["கிருத்திகை", "பூரம்", "உத்திரம்", "பூராடம்", "உத்திராடம்", "பூரட்டாதி"],
    3: ["அஸ்வினி", "புனர்பூசம்", "மகம்", "சுவாதி"],
    4: ["அஸ்வினி", "ஹஸ்தம்", "மூலம்"],
    5: ["ரோகிணி", "மகம்", "சதயம்"],
}
_MARANA = {
    6: ["மகம்", "விசாகம்", "அனுஷம்", "கேட்டை", "அவிட்டம்"],
    0: ["கிருத்திகை", "மகம்", "விசாகம்", "பூராடம்", "உத்திராடம்", "பூரட்டாதி"],
    1: ["திருவாதிரை", "விசாகம்", "கேட்டை", "சதயம்", "பூரட்டாதி"],
    2: ["அஸ்வினி", "ஹஸ்தம்", "மூலம்", "ரேவதி"],
    3: ["கிருத்திகை", "ரோகிணி", "மிருகசீரிடம்", "திருவாதிரை", "உத்திரம்", "சதயம்"],
    4: ["ரோகிணி", "பூசம்", "ஆயில்யம்", "மகம்", "கேட்டை", "திருவோணம்"],
    5: ["ஆயில்யம்", "உத்திரம்", "ஹஸ்தம்", "சித்திரை", "பூரட்டாதி"],
}
_PRABALA = {6: "பரணி", 0: "சித்திரை", 1: "உத்திராடம்", 2: "அவிட்டம்", 3: "கேட்டை", 4: "பூராடம்", 5: "ரேவதி"}


def amirthathi(weekday: int, nak_idx: int) -> str:
    name = T.NAKSHATRAS_TA[nak_idx]
    if name in _AMIRTHA[weekday]:
        return "அமிர்த யோகம்"
    if name in _MARANA[weekday]:
        return "மரண யோகம்"
    if name == _PRABALA[weekday]:
        return "பிரபலாரிஷ்ட யோகம்"
    return "சித்த யோகம்"


def nokku(nak_idx: int) -> str:
    return "மேல் நோக்கு நாள்" if nak_idx in MEL_NOKKU else "கீழ் நோக்கு நாள்" if nak_idx in KEEL_NOKKU else "சம நோக்கு நாள்"


# ----------------------------------------------------------------------------- lay-man Tamil time text
def part_of_day_ta(t: dt.datetime) -> str:
    h = t.hour + t.minute / 60
    if h < 3:
        return "இரவு"
    if h < 6:
        return "அதிகாலை"
    if h < 12:
        return "காலை"
    if h < 15:
        return "மதியம்"
    if h < 18:
        return "மாலை"
    return "இரவு"


def time_ta(t: dt.datetime, day: dt.date) -> str:
    """'இன்று மாலை 01.11', 'நாளை காலை 04.31', 'நேற்று இரவு 07.20'."""
    # printed calendars treat 00:00–03:00 as the previous evening's "இரவு"
    ref = t.date() - dt.timedelta(days=1) if t.hour < 3 else t.date()
    n = (ref - day).days
    rel = "இன்று" if n == 0 else "நாளை" if n == 1 else "நேற்று" if n == -1 else ref.strftime("%d-%m")
    return f"{rel} {part_of_day_ta(t)} {t.strftime('%I.%M')}"


def chain_sentence(items: list[dict], day: dt.date, zone: ZoneInfo, key: str = "name_ta") -> str:
    """'இன்று மதியம் 01.11 வரை அஷ்டமி, பின்பு நவமி' / 'இன்று முழுவதும் ஆயில்யம்'."""
    if not items:
        return ""
    first = items[0]
    if not first.get("end_iso"):
        return f"இன்று முழுவதும் {first[key]}"
    end = dt.datetime.fromisoformat(first["end_iso"]).astimezone(zone)
    s = f"{time_ta(end, day)} வரை {first[key]}"
    if len(items) > 1:
        s += f", பின்பு {items[1][key]}"
        if len(items) > 2 and items[1].get("end_iso"):
            e2 = dt.datetime.fromisoformat(items[1]["end_iso"]).astimezone(zone)
            s += f" ({time_ta(e2, day)} வரை), பின்பு {items[2][key]}"
    return s


# ----------------------------------------------------------------------------- astronomy
def _asc(jd: float, lat: float, lon: float) -> float:
    return E.norm(swe.houses_ex(jd, lat, lon, b"W", swe.FLG_SIDEREAL)[1][0])


def _asc_next_sign(jd0: float, lat: float, lon: float) -> float:
    """Instant when the ascendant enters the next sign (asc moves ~1 sign / 2 h, always forward)."""
    s0 = int(_asc(jd0, lat, lon) / 30)
    target = (s0 + 1) % 12
    lo, hi = jd0, jd0 + 3 / 24
    while int(_asc(hi, lat, lon) / 30) == s0:
        hi += 1 / 24
    for _ in range(40):
        mid = (lo + hi) / 2
        if int(_asc(mid, lat, lon) / 30) == s0:
            lo = mid
        else:
            hi = mid
    return hi


def lagna_table(rise: float, next_rise: float, lat: float, lon: float, zone: ZoneInfo, day: dt.date) -> list[dict]:
    out, jd = [], rise
    while jd < next_rise and len(out) < 13:
        s = int(_asc(jd, lat, lon) / 30)
        end = _asc_next_sign(jd, lat, lon)
        a, b = E_to_local(jd, zone), E_to_local(end, zone)
        out.append({"sign_index": s, "sign_ta": T.SIGNS_TA[s], "start": _hmd(a, day), "end": _hmd(b, day),
                    "start_iso": a.isoformat(), "end_iso": b.isoformat()})
        jd = end + 1e-6
    return out


def E_to_local(jd: float, zone: ZoneInfo) -> dt.datetime:
    y, m, d, h = swe.revjul(jd)
    return (dt.datetime(y, m, d, tzinfo=dt.timezone.utc) + dt.timedelta(hours=h)).astimezone(zone)


def _hmd(t: dt.datetime, day: dt.date) -> str:
    s = t.strftime("%H:%M")
    n = (t.date() - day).days
    return s if n == 0 else f"{s} (+{n})"


def nazhigai(minutes: float) -> dict:
    """1 நாழிகை = 24 min; 1 விநாடி = 1/60 நாழிகை = 24 s."""
    total_vinadi = round(minutes * 60 / 24)
    return {"nazhigai": total_vinadi // 60, "vinadi": total_vinadi % 60,
            "text_ta": f"{total_vinadi // 60:02d} நாழிகை {total_vinadi % 60:02d} விநாடி"}


def gochara(rise: float, lat: float, lon: float, zone: ZoneInfo, day: dt.date) -> dict:
    """Transit chart at sunrise + next sign change of every planet within 60 days (for the chart's centre notes)."""
    pos = E._positions(rise, "mean")
    pos["Lagna"] = {"lon": _asc(rise, lat, lon), "speed": 0.0, "retrograde": False}
    out = {}
    for p, v in pos.items():
        n, pada = E.nakshatra_of(v["lon"])
        out[p] = {"name_ta": T.PLANETS_TA.get(p, "லக்னம்"), "short_ta": T.PLANETS_TA_SHORT.get(p, "லக்"),
                  "lon": round(v["lon"], 4), "sign_index": E.sign_index(v["lon"]), "sign_ta": T.SIGNS_TA[E.sign_index(v["lon"])],
                  "deg_in_sign": E.dms(v["lon"] % 30), "nakshatra_ta": T.NAKSHATRAS_TA[n], "pada": pada,
                  "retrograde": v["retrograde"]}
    # next ingress for the real planets (Rahu/Ketu move backwards)
    bodies = dict(E.SWE_BODY)
    bodies["Rahu"] = swe.MEAN_NODE
    ingress = []
    for p, body in bodies.items():
        lon0 = E.norm(swe.calc_ut(rise, body, E.EPH_FLAG | swe.FLG_SIDEREAL)[0][0])
        s0 = int(lon0 / 30)
        found = None
        t = rise
        for _ in range(60):
            t2 = t + 1
            l2 = E.norm(swe.calc_ut(t2, body, E.EPH_FLAG | swe.FLG_SIDEREAL)[0][0])
            if int(l2 / 30) != s0:
                lo, hi = t, t2
                for _ in range(30):
                    mid = (lo + hi) / 2
                    lm = E.norm(swe.calc_ut(mid, body, E.EPH_FLAG | swe.FLG_SIDEREAL)[0][0])
                    if int(lm / 30) == s0:
                        lo = mid
                    else:
                        hi = mid
                found = (hi, int(l2 / 30))
                break
            t = t2
        if found:
            when = E_to_local(found[0], zone)
            rec = {"planet": p, "planet_ta": T.PLANETS_TA[p], "sign_index": found[1], "sign_ta": T.SIGNS_TA[found[1]],
                   "date": when.date().isoformat(), "date_display": when.strftime("%d-%m-%Y"), "time": when.strftime("%H:%M"),
                   "text_ta": f"{when.strftime('%d-%m')} {T.SIGNS_TA[found[1]]} – {T.PLANETS_TA[p]}"}
            ingress.append(rec)
            if p == "Rahu":
                ks = (found[1] + 6) % 12
                ingress.append({"planet": "Ketu", "planet_ta": T.PLANETS_TA["Ketu"], "sign_index": ks, "sign_ta": T.SIGNS_TA[ks],
                                "date": rec["date"], "date_display": rec["date_display"], "time": rec["time"],
                                "text_ta": f"{when.strftime('%d-%m')} {T.SIGNS_TA[ks]} – கேது"})
    ingress.sort(key=lambda r: r["date"])
    return {"positions": out, "next_ingress": ingress,
            "by_sign": [[out[p]["short_ta"] for p in out if out[p]["sign_index"] == s and p != "Lagna"] for s in range(12)]}


# ----------------------------------------------------------------------------- assemble
def extras(*, rise: float, sett: float, next_rise: float, lat: float, lon: float, zone: ZoneInfo, day: dt.date,
           weekday: int, sun_sign: int, moon_sign: int, tithis: list, naks: list, yogas: list, karanas: list) -> dict:
    sunrise = E_to_local(rise, zone)
    # day's nakshatra = the one covering the larger share of daylight
    def share(items):
        best, best_len, t0 = items[0], -1.0, rise
        for it in items:
            if it.get("end_iso"):
                e = dt.datetime.fromisoformat(it["end_iso"]).astimezone(dt.timezone.utc)
                ejd = swe.julday(e.year, e.month, e.day, e.hour + e.minute / 60 + e.second / 3600)
            else:
                ejd = next_rise
            seg = max(0.0, min(ejd, sett) - t0)
            if seg > best_len:
                best, best_len = it, seg
            t0 = ejd
            if t0 >= sett:
                break
        return best
    day_nak = share(naks)
    nak_idx = day_nak["index"] - 1

    # amirthathi chain by nakshatra segments (weekday fixed from sunrise to next sunrise)
    am_items = []
    for it in naks:
        am_items.append({"name_ta": amirthathi(weekday, it["index"] - 1), "end_iso": it.get("end_iso"), "end_time": it.get("end_time")})
    # merge consecutive identical yogams
    merged = []
    for it in am_items:
        if merged and merged[-1]["name_ta"] == it["name_ta"]:
            merged[-1]["end_iso"], merged[-1]["end_time"] = it["end_iso"], it["end_time"]
        else:
            merged.append(dict(it))

    # chandrashtama: birth star = transit star + 11 (same thing as the 8th rasi from the Moon sign)
    ch_items = [{"name_ta": T.NAKSHATRAS_TA[(it["index"] - 1 + 11) % 27], "end_iso": it.get("end_iso"), "end_time": it.get("end_time")} for it in naks]
    ch_rasi = (moon_sign + 5) % 12          # the rasi for which the Moon sign is the 8th house (rasi + 7 ≡ moon_sign)

    # tithi start (previous crossing) for the "நேற்று இரவு 07.20 முதல்" phrasing
    from .panchang import _elong, _prev_crossing  # local import to avoid a cycle
    t_start = _prev_crossing(_elong, rise, 12.0)
    t_start_local = E_to_local(t_start, zone) if t_start else None

    # lagna at sunrise and remaining time
    asc0 = _asc(rise, lat, lon)
    asc_end = _asc_next_sign(rise, lat, lon)
    remaining_min = (asc_end - rise) * 1440

    ayanam = "உத்தராயணம்" if sun_sign in (9, 10, 11, 0, 1, 2) else "தட்சிணாயணம்"
    paksha = "வளர்பிறை" if tithis[0]["index"] <= 15 else "தேய்பிறை"
    sentences = {
        "tithi": chain_sentence(tithis, day, zone), "nakshatra": chain_sentence(naks, day, zone),
        "yoga": chain_sentence(yogas, day, zone), "karana": chain_sentence(karanas, day, zone),
        "amirthathi": chain_sentence(merged, day, zone), "chandrashtamam": chain_sentence(ch_items, day, zone),
    }
    tithi_banner = f"{paksha} {tithis[0]['name_ta']}"
    if t_start_local and tithis[0].get("end_iso"):
        e = dt.datetime.fromisoformat(tithis[0]["end_iso"]).astimezone(zone)
        tithi_banner += f" ({time_ta(t_start_local, day)} முதல் {time_ta(e, day)} வரை)"

    def slots(tbl):
        return [{"start": a, "end": b, "label": "காலை" if int(a[:2]) < 12 else "மாலை"} for a, b in tbl]

    return {
        "ayanam_ta": ayanam, "paksha_ta": paksha, "tithi_banner_ta": tithi_banner,
        "nokku_ta": nokku(nak_idx), "day_nakshatra_ta": day_nak["name_ta"],
        "chandrashtamam": {"rasi_ta": T.SIGNS_TA[ch_rasi], "text_ta": sentences["chandrashtamam"], "items": ch_items,
                           "rule": "birth star = transit star + 11 (equivalently the 8th rasi from the transiting Moon)"},
        "amirthathi_yogam": {"text_ta": sentences["amirthathi"], "items": merged, "rule": "weekday × nakshatra table"},
        "sentences_ta": sentences,
        "nalla_neram": slots(NALLA_NERAM[weekday]), "gowri_nalla_neram": slots(GOWRI_NERAM[weekday]),
        "nalla_neram_note_ta": "பாரம்பரிய அட்டவணை (கிழமை அடிப்படையில் நிலையான நேரம்)",
        "soolam_ta": SOOLAM[weekday], "parigaram_ta": PARIGARAM[weekday],
        "lagna_at_sunrise": {"sign_index": int(asc0 / 30), "sign_ta": T.SIGNS_TA[int(asc0 / 30)], "deg_in_sign": E.dms(asc0 % 30),
                             "remaining": nazhigai(remaining_min), "ends": E_to_local(asc_end, zone).strftime("%H:%M"),
                             "text_ta": f"{T.SIGNS_TA[int(asc0 / 30)]} லக்னம் இருப்பு {nazhigai(remaining_min)['text_ta']}"},
        "lagna_table": lagna_table(rise, next_rise, lat, lon, zone, day),
        "gochara": gochara(rise, lat, lon, zone, day),
    }
