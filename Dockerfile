# ── AI Client Finder — Backend (FastAPI + Playwright + ffmpeg) ──────────────
# Build context = repo root.  App is imported as `backend.main:app`.
FROM python:3.13-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright

WORKDIR /app

# System deps: ffmpeg for the video module.
RUN apt-get update && apt-get install -y --no-install-recommends \
        ffmpeg \
        ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Python deps (layer cached unless requirements change).
COPY backend/requirements.txt ./backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt

# Chromium + its OS libraries for Playwright (version auto-matches the pip install).
RUN python -m playwright install --with-deps chromium

# App code.
COPY backend ./backend

EXPOSE 8000

# Single worker: apscheduler runs in-process, multiple workers would duplicate jobs.
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
