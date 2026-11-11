# தமிழ் ஜாதகம் — calculation API (backend)

Deterministic Vedic chart calculations for the Tamil horoscope web app.
Every number comes from **Swiss Ephemeris 2.10.03** (pyswisseph 2.10.3.2) — no AI involvement.

| Setting | பாரம்பரிய ஜோதிடம் (`mode=traditional`) | கே.பி. ஜோதிடம் (`mode=kp`) |
|---|---|---|
| Ayanamsa | Lahiri (`SIDM_LAHIRI`, id 1) | Krishnamurti (`SIDM_KRISHNAMURTI`, id 5) |
| Houses | Whole-sign Rasi houses | Placidus cusps |
| Rahu/Ketu | Mean node (`node=true` also available) | same |
| Dasha | Vimshottari, 365.25-day years, 3 levels | same |
| Extras | Navamsa, panchang, transits | star / sub / sub-sub lords, cusps, ABCD significators |

Both modes share one astronomical engine; only the settings and presentation differ.
The response's `calculation` block states engine, ephemeris data, ayanamsa id + value, house system,
node convention, dasha year length, timezone id, resolved UTC offset and `calculation_version`.

## Endpoints
- `GET  /health`
- `GET  /api/v1/places?q=chennai` – offline place search (GeoNames cities ≥15k, Tamil names work: `சென்னை`)
- `GET  /api/v1/timezone?latitude=..&longitude=..&date=yyyy-mm-dd` – IANA zone + **historical** UTC offset for that date
- `POST /api/v1/chart` – body: `{name, gender?, date:"yyyy-mm-dd", time:"hh:mm:ss", tz_id, latitude, longitude, mode, node?, as_of?}`

Birth details are never written to logs or disk.

## Run locally (no Docker)
```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
ALLOWED_ORIGINS=http://localhost:5173 uvicorn app.main:app --port 8000
python -m pytest -q tests            # 17 tests
```

## Deploy on your VPS with Docker (simple steps)
1. Copy this folder to the server (e.g. `scp -r tamil-jathagam-api user@server:~/`).
2. `cp .env.example .env` and put your Lovable site URL(s) in `ALLOWED_ORIGINS`.
3. `docker compose up -d --build`  → API listens on `127.0.0.1:8000`.
4. Put HTTPS in front with Caddy (easiest) — `/etc/caddy/Caddyfile`:
   ```
   jathagam-api.yourdomain.in {
       reverse_proxy 127.0.0.1:8000
   }
   ```
   then `systemctl reload caddy`. Point a DNS A-record `jathagam-api` at the server first.
5. Check `https://jathagam-api.yourdomain.in/health`.
6. In Lovable → project settings → environment variables set `VITE_API_BASE_URL=https://jathagam-api.yourdomain.in`.

## Tests (what is verified)
- Planet longitudes, lagna, nakshatra/pada for the reference chart match the TP Tamil app to the arc-second
- Vimshottari dates & current Dasa–Bhukti–Antara match the reference (balance boundary ±1 day, see note)
- KP planets, star/sub/sub-sub lords and Placidus cusps match diliprk/VedicAstro (same settings)
- Seconds preserved; historical offsets (India +06:30 in 1943, US DST) applied by birth date
- Sign / nakshatra / pada / navamsa boundary cases; dasha tree chronological and nested; determinism
- Not verified: Maandi/Gulika (not provided), divisional charts beyond D9, significator edge rules (Rahu/Ketu agency)

Note: the TP app rounds the first dasha boundary to the nearest day; this engine keeps the exact instant and
formats the date from it, so that one boundary can differ by one day.

## Licences — read before going commercial
- This backend code: MIT.
- **Swiss Ephemeris and pyswisseph are AGPL-3.0** (Astrodienst dual-licenses Swiss Ephemeris; pyswisseph is AGPL only).
  Running an AGPL engine behind a closed-source web service is **not** allowed by AGPL: either publish this
  backend's source under AGPL (fine — it is a separate service), or buy the Swiss Ephemeris professional licence
  from Astrodienst. The `.se1` data files in `ephe/` are Astrodienst's and carry the same terms.
- GeoNames data (place search): CC BY 4.0 — credit GeoNames in the app footer.
- diliprk/VedicAstro (MIT) and its flatlib fork (MIT) are used only as an offline cross-check in the tests.

## Daily features (v1.1)

| Endpoint | What |
|---|---|
| `GET /api/v1/panchang?date=&latitude=&longitude=&tz_id=&place=` | தினசரி பஞ்சாங்கம் (defaults: today in Chennai). Tamil date, weekday, tithi/nakshatra/yoga/karana chains with end times, sunrise/sunset, Rahu/Yama/Gulikai. Cached per date+location+zone. |
| `GET /api/v1/rasi-palan?date=` | Public: இன்றைய ராசி பலன்கள் for the date — open, no approval step. |
| `GET /api/v1/admin/rasi-palan?date=` (header `x-admin-token`) | Preview the draft with every rule that fired. |
| `POST /api/v1/admin/rasi-palan/approve` `{date, approver, edits?}` | Optional: save edited Tamil text per rasi (overrides the generated text). |
| `POST /api/v1/admin/rasi-palan/unpublish` `{date}` | Take a day back to draft. |

Rules live in `app/palan.py` (`FAVOURABLE` table + Tamil templates). Set `ADMIN_TOKEN` in `.env`. Drafts are saved in `data/palan/<date>.json`.

### Panchangam extras (v1.2)
`/api/v1/panchang` additionally returns: `ayanam_ta`, `paksha_ta`, `tithi_banner_ta`, `sentences_ta` (lay-man Tamil sentences for tithi/nakshatra/yoga/karana/amirthathi/chandrashtamam), `nokku_ta`, `day_nakshatra_ta`, `chandrashtamam`, `amirthathi_yogam`, `nalla_neram`, `gowri_nalla_neram` (fixed weekday table, printed-calendar convention), `soolam_ta`, `parigaram_ta`, `lagna_at_sunrise` (with remaining நாழிகை), `lagna_table`, `gochara` (sunrise transit chart + next ingress dates).
Not provided: நேத்திரம்/ஜீவன் (published sources disagree on the rule). Sources for the fixed tables: nallaneramtoday.com (weekday நல்ல நேரம்/கௌரி), thirukanithapanchangam.com (சூலம்/பரிகாரம்), ungalvazhkkai.seithisaral.in (அமிர்தாதி யோகம்).
