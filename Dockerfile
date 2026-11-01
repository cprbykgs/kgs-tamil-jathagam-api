# தமிழ் ஜாதகம் calculation API — Swiss Ephemeris (pyswisseph) + FastAPI
FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /srv
# build tools are needed only to compile pyswisseph; removed afterwards to keep the image small
COPY requirements.txt .
RUN apt-get update && apt-get install -y --no-install-recommends gcc libc6-dev \
 && pip install --no-cache-dir -r requirements.txt \
 && apt-get purge -y gcc libc6-dev && apt-get autoremove -y && rm -rf /var/lib/apt/lists/*
COPY app ./app
COPY ephe ./ephe
ENV EPHE_DIR=/srv/ephe ALLOWED_ORIGINS=http://localhost:5173 PORT=8000
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s CMD python -c "import urllib.request;urllib.request.urlopen('http://127.0.0.1:8000/health')" || exit 1
# one worker: Swiss Ephemeris keeps global state and the engine serialises calculations with a lock
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT} --workers 1"]
