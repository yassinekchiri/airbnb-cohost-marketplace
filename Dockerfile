# syntax=docker/dockerfile:1
FROM python:3.15-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Chromium for the Airbnb scraper (moves to its own worker image in Phase 6)
RUN apt-get update && apt-get install -y --no-install-recommends \
    chromium chromium-driver \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

# Run as an unprivileged user
RUN useradd --system --uid 10001 --create-home app \
    && mkdir -p /app/logs /app/media /app/staticfiles \
    && chown -R app:app /app

COPY --chown=app:app . .
USER app

# Placeholder secrets exist only for this build step and are not kept in the image.
RUN SECRET_KEY=build-placeholder DEBUG=False ALLOWED_HOSTS=localhost LOG_TO_FILE=False \
    python manage.py collectstatic --noinput

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD python -c "import urllib.request as u; u.urlopen('http://127.0.0.1:8000/healthz', timeout=3)" || exit 1

CMD ["gunicorn", "--config", "gunicorn.conf.py", "helloworld.wsgi:application"]
