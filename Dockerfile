FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Chromium for the Airbnb scraper
RUN apt-get update && apt-get install -y --no-install-recommends \
    chromium \
    chromium-driver \
    && rm -rf /var/lib/apt/lists/*

# Python deps
COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

# App source
COPY . .

# Collect static files (needs SECRET_KEY at build time — use a placeholder)
RUN SECRET_KEY=build-placeholder DEBUG=False ALLOWED_HOSTS=localhost \
    python manage.py collectstatic --noinput

# Runtime directories
RUN mkdir -p logs media

EXPOSE 8000

CMD ["gunicorn", "--config", "gunicorn.conf.py", "helloworld.wsgi:application"]
