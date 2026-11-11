# -*- coding: utf-8 -*-
"""
இன்றைய ராசி பலன்கள் — rule-based daily readings for the 12 Moon signs.

How it works (fully inspectable):
  1. Transit (gochara) positions are computed for the date at sunrise, Chennai, Lahiri (Swiss Ephemeris).
  2. For each Moon sign (ராசி) we find the house (1–12) each transiting planet occupies counted from that sign.
  3. The classical gochara table below says whether that house is favourable for that planet.
  4. Each fired rule contributes an original Tamil sentence to one of three sections
     (general / work / relationships) and ±1 to a score.  Sections are assembled from the
     fired sentences; the score becomes a 1–5 rating.
  5. Special flags: Chandrashtama (Moon in 8th), Sade-sati (Saturn in 12/1/2), Ashtama Sani (8),
     Ardhashtama Sani (4), Guru balam (Jupiter in 2/5/7/9/11).
  Readings are DRAFTS until an admin approves them; the public endpoint only returns approved sets.
  These are general sign-level guidance, never personal predictions — the disclaimer travels with the data.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import secrets
from zoneinfo import ZoneInfo

import swisseph as swe

from . import engine as E
from . import tamil as T

RULES_VERSION = "1.0.0"
DATA_DIR = os.environ.get("DATA_DIR", os.path.join(os.path.dirname(__file__), "..", "data"))
CHENNAI = dict(lat=13.0827, lon=80.2707, tz_id="Asia/Kolkata")

# Classical gochara: houses (from the Moon sign) where each transiting planet is favourable.
FAVOURABLE = {
    "Sun": {3, 6, 10, 11}, "Moon": {1, 3, 6, 7, 10, 11}, "Mars": {3, 6, 11}, "Mercury": {2, 4, 6, 8, 10, 11},
    "Jupiter": {2, 5, 7, 9, 11}, "Venus": {1, 2, 3, 4, 5, 8, 9, 11, 12}, "Saturn": {3, 6, 11}, "Rahu": {3, 6, 11}, "Ketu": {3, 6, 11},
}
SECTION = {"Sun": "work", "Moon": "general", "Mars": "work", "Mercury": "work", "Jupiter": "general",
           "Venus": "relationships", "Saturn": "work", "Rahu": "general", "Ketu": "relationships"}

# Original Tamil templates. {h} = house number. Keep them short, neutral and advisory.
GOOD = {
    "Sun": "சூரியன் {h}-ஆம் வீட்டில்: அதிகாரிகளின் ஆதரவும் உற்சாகமும் கூடும்.",
    "Moon": "சந்திரன் {h}-ஆம் வீட்டில்: மனநிலை தெளிவாக இருக்கும்; எடுக்கும் முடிவுகள் கைகூடும்.",
    "Mars": "செவ்வாய் {h}-ஆம் வீட்டில்: செயலாற்றல் கூடும்; தள்ளிப்போன பணிகளை முடிக்க ஏற்ற நாள்.",
    "Mercury": "புதன் {h}-ஆம் வீட்டில்: பேச்சு, எழுத்து, கணக்கு சார்ந்த வேலைகள் சுமூகமாக நடக்கும்.",
    "Jupiter": "குரு {h}-ஆம் வீட்டில்: பெரியவர்களின் ஆசியும் நல்ல செய்திகளும் வரும்.",
    "Venus": "சுக்கிரன் {h}-ஆம் வீட்டில்: உறவுகளில் இனிமை; குடும்பத்தில் மகிழ்ச்சி.",
    "Saturn": "சனி {h}-ஆம் வீட்டில்: கடின உழைப்புக்கு ஏற்ற பலன் கிடைக்கும்.",
    "Rahu": "ராகு {h}-ஆம் வீட்டில்: புதிய தொடர்புகள் மூலம் அனுகூலம்.",
    "Ketu": "கேது {h}-ஆம் வீட்டில்: மன அமைதிக்கும் ஆன்மிக நாட்டத்திற்கும் உகந்த நாள்.",
}
BAD = {
    "Sun": "சூரியன் {h}-ஆம் வீட்டில்: பணியிடத்தில் அவசர முடிவுகளைத் தவிர்க்கவும்.",
    "Moon": "சந்திரன் {h}-ஆம் வீட்டில்: மனக்குழப்பம் ஏற்படலாம்; முக்கிய முடிவுகளை ஒத்திவைக்கலாம்.",
    "Mars": "செவ்வாய் {h}-ஆம் வீட்டில்: சொல்லிலும் செயலிலும் பொறுமை தேவை.",
    "Mercury": "புதன் {h}-ஆம் வீட்டில்: ஆவணங்களை இருமுறை சரிபார்க்கவும்.",
    "Jupiter": "குரு {h}-ஆம் வீட்டில்: எதிர்பார்ப்புகளைக் குறைத்து நிதானமாகச் செயல்படவும்.",
    "Venus": "சுக்கிரன் {h}-ஆம் வீட்டில்: உறவுகளில் சிறு மனக்கசப்பு வரலாம்; அன்புடன் பேசவும்.",
    "Saturn": "சனி {h}-ஆம் வீட்டில்: வேலைப்பளு கூடும்; உடல்நலத்தில் கவனம்.",
    "Rahu": "ராகு {h}-ஆம் வீட்டில்: அவசரத் தீர்மானங்களும் வதந்திகளும் வேண்டாம்.",
    "Ketu": "கேது {h}-ஆம் வீட்டில்: நெருங்கியவர்களிடம் தெளிவாகப் பேசுவது நல்லது.",
}
FLAGS = {
    "chandrashtama": "இன்று சந்திராஷ்டமம்: முக்கியப் பயணம், புதிய முயற்சிகளைத் தவிர்த்து எளிமையாக நாளைக் கழிக்கவும்.",
    "sade_sati": "ஏழரைச் சனி காலம் நடக்கிறது: பொறுமையும் ஒழுங்கும் பலன் தரும்.",
    "ashtama_sani": "அஷ்டமச் சனி காலம்: உடல்நலம், பண விஷயங்களில் எச்சரிக்கை.",
    "ardhashtama_sani": "அர்த்தாஷ்டமச் சனி: குடும்ப, வீட்டு விஷயங்களில் நிதானம் தேவை.",
    "guru_balam": "குரு பலம் உண்டு: தொடங்கும் நல்ல காரியங்கள் கைகூடும்.",
}
RATING_TA = {1: "கவனம் தேவை", 2: "சுமார்", 3: "நடுத்தரம்", 4: "நல்ல நாள்", 5: "மிகச் சிறந்த நாள்"}
DISCLAIMER_TA = ("இது சந்திர ராசி அடிப்படையிலான பொதுவான கோசார வழிகாட்டல் மட்டுமே; தனிநபர் ஜாதகப் பலன் அல்ல. "
                 "உறுதியான முன்னறிவிப்பு அல்ல — முடிவுகளுக்கு உங்கள் விவேகமே முதன்மை.")


def _transits(date: str, lat: float, lon: float, tz_id: str) -> dict:
    """Sidereal transit positions at local sunrise on the date."""
    zone = ZoneInfo(tz_id)
    day = dt.date.fromisoformat(date)
    off = dt.datetime(day.year, day.month, day.day, tzinfo=zone).utcoffset().total_seconds() / 86400
    jd_mid = swe.julday(day.year, day.month, day.day, 0) - off
    with E._LOCK:
        swe.set_sid_mode(swe.SIDM_LAHIRI, 0, 0)
        rise = swe.rise_trans(jd_mid, swe.SUN, swe.CALC_RISE, (lon, lat, 0), flags=E.EPH_FLAG)[1][0]
        pos = E._positions(rise, "mean")
    return {"jd": rise, "positions": {p: {"lon": v["lon"], "sign_index": E.sign_index(v["lon"]),
                                        "sign_ta": T.SIGNS_TA[E.sign_index(v["lon"])], "retrograde": v["retrograde"]}
                                     for p, v in pos.items()}}


def _reading(rasi: int, pos: dict) -> dict:
    houses = {p: (v["sign_index"] - rasi) % 12 + 1 for p, v in pos.items()}
    fired, sections, score = [], {"general": [], "work": [], "relationships": []}, 0
    for p in T.PLANETS_EN:
        h = houses[p]
        good = h in FAVOURABLE[p]
        score += 1 if good else -1
        txt = (GOOD if good else BAD)[p].format(h=h)
        sections[SECTION[p]].append(txt)
        fired.append({"planet": p, "planet_ta": T.PLANETS_TA[p], "house": h, "favourable": good, "text_ta": txt})
    flags = []
    if houses["Moon"] == 8:
        flags.append("chandrashtama"); score -= 2
    sat = houses["Saturn"]
    if sat in (12, 1, 2):
        flags.append("sade_sati")
    elif sat == 8:
        flags.append("ashtama_sani")
    elif sat == 4:
        flags.append("ardhashtama_sani")
    if houses["Jupiter"] in (2, 5, 7, 9, 11):
        flags.append("guru_balam")
    for f in flags:
        sections["general"].insert(0, FLAGS[f])
    # map score to 1–5. The classical favourable-house sets are smaller than half the zodiac for most
    # planets, so the expected raw score is about −2; the bands are centred there.
    rating = 1 if score <= -6 else 2 if score <= -4 else 3 if score <= -1 else 4 if score <= 2 else 5
    return {
        "rasi_index": rasi, "rasi_ta": T.SIGNS_TA[rasi], "rasi_en": T.SIGNS_EN[rasi],
        "rating": rating, "rating_ta": RATING_TA[rating], "score": score,
        "general_ta": " ".join(sections["general"]), "work_ta": " ".join(sections["work"]),
        "relationships_ta": " ".join(sections["relationships"]),
        "flags": flags, "rules_fired": fired, "houses": houses,
    }


def _path(date: str) -> str:
    os.makedirs(os.path.join(DATA_DIR, "palan"), exist_ok=True)
    return os.path.join(DATA_DIR, "palan", f"{date}.json")


def _settings_key(lat: float, lon: float, tz_id: str) -> str:
    return hashlib.sha1(f"{lat:.4f},{lon:.4f},{tz_id},lahiri,mean,{RULES_VERSION}".encode()).hexdigest()[:12]


def generate(date: str, lat: float = CHENNAI["lat"], lon: float = CHENNAI["lon"], tz_id: str = CHENNAI["tz_id"]) -> dict:
    """Compute (or load the cached) draft/approved set for a date."""
    key = _settings_key(lat, lon, tz_id)
    p = _path(date)
    if os.path.exists(p):
        with open(p, encoding="utf-8") as f:
            doc = json.load(f)
        if doc.get("settings_key") == key:
            return doc
    tr = _transits(date, lat, lon, tz_id)
    doc = {
        "date": date, "date_display": dt.date.fromisoformat(date).strftime("%d-%m-%Y"),
        "place": {"name_ta": "சென்னை", "latitude": lat, "longitude": lon, "tz_id": tz_id},
        "settings_key": key, "rules_version": RULES_VERSION,
        "calculation": {"engine": E.ENGINE, "ayanamsa": "lahiri", "node": "mean", "reference_time": "local sunrise",
                        "method_ta": "சந்திர ராசியிலிருந்து கிரகங்களின் கோசார வீட்டு நிலையின் அடிப்படையில் (பாரம்பரிய கோசார விதிகள்)"},
        "transits": tr["positions"],
        "readings": [_reading(r, tr["positions"]) for r in range(12)],
        "status": "draft", "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "approved_at": None, "approved_by": None, "label_ta": "பொதுவான ராசி பலன்", "disclaimer_ta": DISCLAIMER_TA,
    }
    with open(p, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, indent=1)
    return doc


def approve(date: str, approver: str, edits: dict | None = None) -> dict:
    """Mark a day's set approved; optional edits = {rasi_index: {general_ta|work_ta|relationships_ta: text}}."""
    doc = generate(date)
    for k, patch in (edits or {}).items():
        r = doc["readings"][int(k)]
        for fld in ("general_ta", "work_ta", "relationships_ta"):
            if fld in patch and isinstance(patch[fld], str) and patch[fld].strip():
                r[fld] = patch[fld].strip(); r["edited"] = True
    doc["status"] = "approved"; doc["approved_at"] = dt.datetime.now(dt.timezone.utc).isoformat(); doc["approved_by"] = approver
    with open(_path(date), "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, indent=1)
    return doc


def unpublish(date: str) -> dict:
    doc = generate(date); doc["status"] = "draft"; doc["approved_at"] = None; doc["approved_by"] = None
    with open(_path(date), "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, indent=1)
    return doc


def check_token(token: str | None) -> bool:
    expected = os.environ.get("ADMIN_TOKEN", "")
    return bool(expected) and token is not None and secrets.compare_digest(token, expected)
