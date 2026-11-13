# Production Readiness Roadmap
# Airbnb Co-Host Marketplace — Execution Instructions for Claude
#
# Each task is self-contained. Tasks within a phase can be done in any order.
# Complete Phase 1 before deploying to any public server.
# ─────────────────────────────────────────────────────────────────────────────

## PHASE 1 — Critical Security (DO FIRST, 1 session)

### TASK 1.1 — Externalize secrets and environment config
**File:** `helloworld/settings.py`

1. Install python-dotenv: add `python-dotenv>=1.0.0` to requirements.txt
2. At the top of settings.py after `from pathlib import Path`, add:
   ```python
   import os
   from dotenv import load_dotenv
   load_dotenv(BASE_DIR / '.env')
   ```
3. Replace line 23 (`SECRET_KEY = 'django-insecure-...'`) with:
   ```python
   SECRET_KEY = os.environ['SECRET_KEY']
   ```
4. Replace line 26 (`DEBUG = True`) with:
   ```python
   DEBUG = os.getenv('DEBUG', 'False') == 'True'
   ```
5. Replace line 28 (`ALLOWED_HOSTS = ['*']`) with:
   ```python
   ALLOWED_HOSTS = os.getenv('ALLOWED_HOSTS', 'localhost,127.0.0.1').split(',')
   ```
6. Create `/root/airbnb_scraper/.env` with:
   ```
   SECRET_KEY=<generate with: python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())">
   DEBUG=True
   ALLOWED_HOSTS=localhost,127.0.0.1
   DATABASE_URL=sqlite:///db.sqlite3
   EMAIL_HOST=smtp.gmail.com
   EMAIL_PORT=587
   EMAIL_HOST_USER=
   EMAIL_HOST_PASSWORD=
   DEFAULT_FROM_EMAIL=noreply@example.com
   SENTRY_DSN=
   ```
7. Create `/root/airbnb_scraper/.env.example` as a copy of `.env` with values blanked out (for git).
8. Add `.env` to `/root/airbnb_scraper/.gitignore` (create .gitignore if missing):
   ```
   .env
   __pycache__/
   *.pyc
   db.sqlite3
   media/
   staticfiles/
   ```

---

### TASK 1.2 — Remove @csrf_exempt from add_listing
**File:** `hello/views.py`, lines 407-409

1. Remove the `@csrf_exempt` decorator from `add_listing` view (line 409).
2. Remove the import of `csrf_exempt` from line 9 if it's only used there — check first with grep: `grep -n csrf_exempt hello/views.py`.
3. The `add_listing.html` template already has `{% csrf_token %}` in the form (verify this is true before removing). If not, add it to the form in `hello/templates/hello/add_listing.html`.

---

### TASK 1.3 — Remove all debug print() statements
**File:** `hello/views.py`, lines 421–429

Delete these 8 lines from inside the `add_listing` POST handler:
```python
print(f"POST data keys: {list(request.POST.keys())}")
print(f"CSRF token in POST: {'csrfmiddlewaretoken' in request.POST}")
print(f"Host header: {request.META.get('HTTP_HOST', 'unknown')}")
print(f"Origin header: {request.META.get('HTTP_ORIGIN', 'unknown')}")
print(f"Referer header: {request.META.get('HTTP_REFERER', 'unknown')}")
print(f"POST data: {request.POST}")
print(f"Form is valid: {form.is_valid()}")
print(f"Form errors: {form.errors}")
```
Also do a global scan: `grep -n "^    print(" hello/views.py` and remove any other debug prints found.

---

### TASK 1.4 — Add production security headers to settings.py
**File:** `helloworld/settings.py`

Add this block at the end of the file, after the existing CSRF configuration:
```python
# Security headers (applied when DEBUG=False / production)
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = 'DENY'

# These only activate when served over HTTPS — safe to set now:
SECURE_SSL_REDIRECT = os.getenv('SECURE_SSL_REDIRECT', 'False') == 'True'
SECURE_HSTS_SECONDS = int(os.getenv('SECURE_HSTS_SECONDS', '0'))
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SESSION_COOKIE_SECURE = os.getenv('SESSION_COOKIE_SECURE', 'False') == 'True'
CSRF_COOKIE_SECURE = os.getenv('CSRF_COOKIE_SECURE', 'False') == 'True'
```

In production `.env`, set:
```
SECURE_SSL_REDIRECT=True
SECURE_HSTS_SECONDS=31536000
SESSION_COOKIE_SECURE=True
CSRF_COOKIE_SECURE=True
```

---

### TASK 1.5 — Add STATIC_ROOT and configure WhiteNoise for static files
**File:** `helloworld/settings.py`

1. Replace the static files section (around line 120):
   ```python
   STATIC_URL = '/static/'
   STATIC_ROOT = BASE_DIR / 'staticfiles'
   STATICFILES_DIRS = [BASE_DIR / 'hello' / 'static'] if (BASE_DIR / 'hello' / 'static').exists() else []
   ```
2. Add `whitenoise>=6.7.0` to requirements.txt.
3. In `MIDDLEWARE` list in settings.py, insert WhiteNoise AFTER SecurityMiddleware (second position):
   ```python
   'django.middleware.security.SecurityMiddleware',
   'whitenoise.middleware.WhiteNoiseMiddleware',   # ADD THIS LINE
   ...
   ```
4. Add to settings.py:
   ```python
   WHITENOISE_USE_FINDERS = True
   STORAGES = {
       "staticfiles": {
           "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
       },
   }
   ```
5. Update `helloworld/urls.py` to always serve media (not just when DEBUG):
   ```python
   # Replace the `if settings.DEBUG:` block with:
   urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
   ```
   **Note:** In true production, media should be served by Nginx or a CDN — this is acceptable for a first deployment.

---

### TASK 1.6 — Create requirements.txt
**Action:** Run in the project directory:
```bash
pip freeze > /root/airbnb_scraper/requirements.txt
```
Then verify it contains at minimum: Django, Pillow, selenium, webdriver-manager, python-dotenv, whitenoise.
Add any missing ones manually.

---

## PHASE 2 — Logging, Error Handling & Monitoring (1 session)

### TASK 2.1 — Configure Django logging
**File:** `helloworld/settings.py`

Add at the end of the file:
```python
# Logging
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {process:d} {thread:d} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
        'file': {
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': BASE_DIR / 'logs' / 'django.log',
            'maxBytes': 1024 * 1024 * 10,  # 10MB
            'backupCount': 5,
            'formatter': 'verbose',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'WARNING',
    },
    'loggers': {
        'django': {
            'handlers': ['console', 'file'],
            'level': os.getenv('DJANGO_LOG_LEVEL', 'WARNING'),
            'propagate': False,
        },
        'hello': {
            'handlers': ['console', 'file'],
            'level': os.getenv('APP_LOG_LEVEL', 'INFO'),
            'propagate': False,
        },
    },
}
```

Create the logs directory:
```bash
mkdir -p /root/airbnb_scraper/logs
touch /root/airbnb_scraper/logs/.gitkeep
```
Add `logs/*.log` to `.gitignore`.

---

### TASK 2.2 — Replace bare except blocks with specific exceptions + logging
**File:** `hello/views.py`

1. Add at the top of views.py after existing imports:
   ```python
   import logging
   logger = logging.getLogger(__name__)
   ```

2. Find all `except Exception as e:` and bare `except:` blocks using:
   ```bash
   grep -n "except Exception\|except:" hello/views.py
   ```

3. For each one, replace the pattern:
   ```python
   except Exception as e:
       messages.error(request, f'...: {str(e)}')
   ```
   with:
   ```python
   except SomeSpecificException:
       messages.error(request, '...')
       return redirect('marketplace_home')
   except Exception:
       logger.exception("Unexpected error in <view_name> for user %s", request.user.id)
       messages.error(request, 'An unexpected error occurred. Please try again.')
   ```

4. The most critical bare excepts to fix (in order):
   - `add_listing` view: wrap scraper call to catch `subprocess.TimeoutExpired` and `json.JSONDecodeError` separately
   - `listing_detail` view: catch `CoHostProfile.DoesNotExist` specifically
   - `custom_login_redirect`: catch `UserProfile.DoesNotExist` specifically

---

### TASK 2.3 — Add Sentry error monitoring
**File:** `helloworld/settings.py` and `requirements.txt`

1. Add to requirements.txt: `sentry-sdk[django]>=2.0.0`
2. Add to the top of `settings.py` after `load_dotenv(...)`:
   ```python
   import sentry_sdk
   SENTRY_DSN = os.getenv('SENTRY_DSN', '')
   if SENTRY_DSN:
       sentry_sdk.init(
           dsn=SENTRY_DSN,
           traces_sample_rate=0.1,
           send_default_pii=False,
       )
   ```
   This is safe — Sentry only activates when `SENTRY_DSN` is set in the environment.

---

### TASK 2.4 — Create custom 404 and 500 error pages
**Files to create:**
- `hello/templates/404.html`
- `hello/templates/500.html`

Template for 404.html — extend base.html and show a friendly "page not found" message with a link back to marketplace_home. Use the same styling as the rest of the site.

Template for 500.html — same but for server errors. Do NOT include `{% load %}` or database-dependent template tags — 500 pages must render without any DB access.

**File:** `helloworld/settings.py` — verify `TEMPLATES[0]['DIRS']` is set to find the root templates dir:
```python
'DIRS': [BASE_DIR / 'templates'],
```

---

## PHASE 3 — Database & Performance (1 session)

### TASK 3.1 — Add missing database indexes
**File:** `hello/models.py`

Add `db_index=True` to these frequently-queried fields:

1. `UserProfile.role` (line 69):
   ```python
   role = models.CharField(max_length=10, choices=USER_ROLES, db_index=True)
   ```

2. `MarketplaceListing.status` (line 123):
   ```python
   status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='looking', db_index=True)
   ```

3. `Proposal.status` (line 215):
   ```python
   status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending', db_index=True)
   ```

4. After making these changes, create and run the migration:
   ```bash
   python manage.py makemigrations --name="add_db_indexes"
   python manage.py migrate
   ```

---

### TASK 3.2 — Fix N+1 queries with prefetch_related
**File:** `hello/views.py`

1. `host_dashboard` view — find the line that fetches listings for a host (around line 366):
   ```python
   # Change from:
   listings = host_profile.marketplace_listings.all()
   # To:
   listings = host_profile.marketplace_listings.prefetch_related('tasks_needed', 'proposals').all()
   ```

2. `cohost_dashboard` view — find the proposals queryset and add:
   ```python
   proposals = cohost_profile.proposals.select_related(
       'listing', 'listing__host__user_profile__user'
   ).prefetch_related('tasks').all()
   ```

3. `inbox` / conversation views — wherever `proposal.messages.all()` is called in a loop, replace with a queryset fetched once outside the loop and grouped by proposal_id.

---

### TASK 3.3 — Add file upload validation
**File:** `hello/views.py`

Add this helper function near the top of views.py (after imports):
```python
MAX_UPLOAD_SIZE = 5 * 1024 * 1024  # 5MB
ALLOWED_IMAGE_TYPES = {'image/jpeg', 'image/png', 'image/webp', 'image/gif'}

def validate_image_upload(file):
    if file.size > MAX_UPLOAD_SIZE:
        raise ValueError(f"File too large. Maximum size is 5MB.")
    if file.content_type not in ALLOWED_IMAGE_TYPES:
        raise ValueError(f"Invalid file type '{file.content_type}'. Allowed: JPEG, PNG, WEBP, GIF.")
```

Then in `edit_listing` view where `request.FILES.get('main_photo')` is used (around line 1248):
```python
photo_file = request.FILES.get('main_photo')
if photo_file:
    try:
        validate_image_upload(photo_file)
    except ValueError as e:
        messages.error(request, str(e))
        return render(request, 'hello/edit_listing.html', {'listing': listing, 'form': form})
```

Apply the same validation to profile photo upload in `edit_profile` view (around line 1400).

---

### TASK 3.4 — Add SSRF protection to scraper URL input
**File:** `hello/views.py`

Add this helper near validate_image_upload:
```python
from urllib.parse import urlparse
import ipaddress

def validate_scraper_url(url):
    try:
        parsed = urlparse(url)
        if parsed.scheme not in ('http', 'https'):
            raise ValueError("URL must use http or https.")
        if 'airbnb.com' not in parsed.netloc:
            raise ValueError("URL must be an Airbnb listing URL.")
        # Block private/internal IPs
        try:
            ip = ipaddress.ip_address(parsed.hostname)
            if ip.is_private or ip.is_loopback or ip.is_reserved:
                raise ValueError("Private IP addresses are not allowed.")
        except ValueError:
            pass  # hostname is a domain name, not an IP — that's fine
    except Exception as e:
        raise ValueError(str(e))
```

In `add_listing` view, before calling the scraper (around line 431), call:
```python
try:
    validate_scraper_url(airbnb_url)
except ValueError as e:
    messages.error(request, str(e))
    return render(request, 'hello/add_listing.html', {'form': form})
```

---

### TASK 3.5 — PostgreSQL configuration (for production deployment)
**File:** `helloworld/settings.py` and `requirements.txt`

1. Add to requirements.txt: `psycopg2-binary>=2.9.0` (or `psycopg[binary]>=3.0` for psycopg3)
2. Replace the `DATABASES` block in settings.py:
   ```python
   import dj_database_url
   
   DATABASES = {
       'default': dj_database_url.config(
           default=f"sqlite:///{BASE_DIR / 'db.sqlite3'}",
           conn_max_age=600,
       )
   }
   ```
3. Add to requirements.txt: `dj-database-url>=2.0.0`
4. In production `.env`, set:
   ```
   DATABASE_URL=postgresql://user:password@localhost:5432/cohost_marketplace
   ```
5. SQLite continues to work in development — no dev changes needed.

---

## PHASE 4 — User Features (1–2 sessions)

### TASK 4.1 — Add password reset flow
**File:** `hello/urls.py`

1. Add these URL patterns (Django's built-in auth views):
   ```python
   from django.contrib.auth import views as auth_views

   # Add inside urlpatterns:
   path('password-reset/', auth_views.PasswordResetView.as_view(
       template_name='hello/password_reset.html',
       email_template_name='hello/emails/password_reset_email.txt',
       subject_template_name='hello/emails/password_reset_subject.txt',
   ), name='password_reset'),
   path('password-reset/done/', auth_views.PasswordResetDoneView.as_view(
       template_name='hello/password_reset_done.html',
   ), name='password_reset_done'),
   path('password-reset/confirm/<uidb64>/<token>/', auth_views.PasswordResetConfirmView.as_view(
       template_name='hello/password_reset_confirm.html',
   ), name='password_reset_confirm'),
   path('password-reset/complete/', auth_views.PasswordResetCompleteView.as_view(
       template_name='hello/password_reset_complete.html',
   ), name='password_reset_complete'),
   ```

2. Create templates:
   - `hello/templates/hello/password_reset.html` — form with email field, extends base.html
   - `hello/templates/hello/password_reset_done.html` — "check your email" page
   - `hello/templates/hello/password_reset_confirm.html` — new password form
   - `hello/templates/hello/password_reset_complete.html` — success page
   - `hello/templates/hello/emails/password_reset_email.txt` — plain text email body
   - `hello/templates/hello/emails/password_reset_subject.txt` — email subject line

3. Add "Forgot password?" link to `hello/templates/hello/login.html` pointing to `{% url 'password_reset' %}`.

---

### TASK 4.2 — Configure email backend
**File:** `helloworld/settings.py`

Add this block after the LOGGING section:
```python
# Email configuration
EMAIL_BACKEND = os.getenv('EMAIL_BACKEND', 'django.core.mail.backends.console.EmailBackend')
EMAIL_HOST = os.getenv('EMAIL_HOST', 'smtp.gmail.com')
EMAIL_PORT = int(os.getenv('EMAIL_PORT', '587'))
EMAIL_USE_TLS = True
EMAIL_HOST_USER = os.getenv('EMAIL_HOST_USER', '')
EMAIL_HOST_PASSWORD = os.getenv('EMAIL_HOST_PASSWORD', '')
DEFAULT_FROM_EMAIL = os.getenv('DEFAULT_FROM_EMAIL', 'noreply@example.com')
SERVER_EMAIL = DEFAULT_FROM_EMAIL
```

In development, `console.EmailBackend` prints emails to the terminal — no SMTP config needed.
In production `.env`, set `EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend` plus SMTP credentials.

---

### TASK 4.3 — Register all models in Django admin
**File:** `hello/admin.py`

Replace the entire file with:
```python
from django.contrib import admin
from .models import (
    AirbnbListing, DetailedAirbnbListing, UserProfile, HostProfile,
    CoHostProfile, MarketplaceListing, Task, Proposal, Message,
    DirectConversation, DirectMessage, Review, UserSocialLink,
)

@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'role', 'created_at')
    list_filter = ('role',)
    search_fields = ('user__username', 'user__email', 'user__first_name')

@admin.register(MarketplaceListing)
class MarketplaceListingAdmin(admin.ModelAdmin):
    list_display = ('title', 'location', 'status', 'host', 'created_at')
    list_filter = ('status', 'property_type')
    search_fields = ('title', 'location', 'airbnb_url')

@admin.register(Proposal)
class ProposalAdmin(admin.ModelAdmin):
    list_display = ('cohost', 'listing', 'status', 'rate_type', 'offered_rate', 'created_at')
    list_filter = ('status', 'rate_type')

@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = ('name', 'usage_count', 'created_at')
    ordering = ('-usage_count',)

@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ('reviewer', 'reviewee', 'rating', 'created_at')
    list_filter = ('rating',)

admin.site.register(HostProfile)
admin.site.register(CoHostProfile)
admin.site.register(Message)
admin.site.register(DirectConversation)
admin.site.register(DirectMessage)
admin.site.register(UserSocialLink)
admin.site.register(AirbnbListing)
admin.site.register(DetailedAirbnbListing)
```

---

### TASK 4.4 — Add rate limiting to sensitive endpoints
**File:** `hello/views.py`, `requirements.txt`

1. Add to requirements.txt: `django-ratelimit>=4.1.0`
2. Add to `INSTALLED_APPS` in settings.py: `'django_ratelimit'`
3. Apply decorators to these views:
   ```python
   from django_ratelimit.decorators import ratelimit

   # Login — 10 attempts per 5 minutes per IP
   @ratelimit(key='ip', rate='10/5m', method='POST', block=True)
   def login_view(request): ...

   # Message send — 30 per hour per user
   @ratelimit(key='user', rate='30/h', method='POST', block=True)
   def send_message(request, proposal_id): ...

   # Task autocomplete — 60 per minute per IP
   @ratelimit(key='ip', rate='60/m', method='GET', block=True)
   def task_autocomplete(request): ...

   # add_listing — 5 per hour per user (scraper is slow/expensive)
   @ratelimit(key='user', rate='5/h', method='POST', block=True)
   def add_listing(request): ...
   ```

---

## PHASE 5 — Deployment Infrastructure (1 session)

### TASK 5.1 — Create Gunicorn config
**Create:** `/root/airbnb_scraper/gunicorn.conf.py`
```python
bind = "0.0.0.0:8000"
workers = 4
worker_class = "sync"
worker_connections = 1000
max_requests = 1000
max_requests_jitter = 50
timeout = 30
keepalive = 5
errorlog = "logs/gunicorn_error.log"
accesslog = "logs/gunicorn_access.log"
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s'
```

Add to requirements.txt: `gunicorn>=22.0.0`

---

### TASK 5.2 — Create Dockerfile
**Create:** `/root/airbnb_scraper/Dockerfile`
```dockerfile
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    chromium chromium-driver \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

COPY . .

RUN python manage.py collectstatic --noinput

RUN mkdir -p logs media

EXPOSE 8000

CMD ["gunicorn", "--config", "gunicorn.conf.py", "helloworld.wsgi:application"]
```

---

### TASK 5.3 — Create docker-compose.yml
**Create:** `/root/airbnb_scraper/docker-compose.yml`
```yaml
version: '3.9'

services:
  db:
    image: postgres:16-alpine
    restart: unless-stopped
    volumes:
      - pgdata:/var/lib/postgresql/data
    environment:
      POSTGRES_DB: cohost_marketplace
      POSTGRES_USER: ${POSTGRES_USER:-cohost}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:?POSTGRES_PASSWORD required}

  web:
    build: .
    restart: unless-stopped
    depends_on:
      - db
    ports:
      - "8000:8000"
    volumes:
      - ./media:/app/media
      - ./logs:/app/logs
    env_file: .env
    environment:
      DATABASE_URL: postgresql://${POSTGRES_USER:-cohost}:${POSTGRES_PASSWORD}@db:5432/cohost_marketplace
    command: >
      sh -c "python manage.py migrate --noinput &&
             gunicorn --config gunicorn.conf.py helloworld.wsgi:application"

volumes:
  pgdata:
```

---

### TASK 5.4 — Create Nginx config (for production with HTTPS)
**Create:** `/root/airbnb_scraper/nginx.conf`
```nginx
server {
    listen 80;
    server_name yourdomain.com www.yourdomain.com;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl http2;
    server_name yourdomain.com www.yourdomain.com;

    ssl_certificate /etc/letsencrypt/live/yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/yourdomain.com/privkey.pem;

    client_max_body_size 10M;

    location /static/ {
        alias /app/staticfiles/;
        expires 1y;
        add_header Cache-Control "public, immutable";
    }

    location /media/ {
        alias /app/media/;
        expires 7d;
    }

    location / {
        proxy_pass http://web:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

---

## PHASE 6 — Async Scraping with Celery (advanced, 1–2 sessions)

### TASK 6.1 — Replace synchronous subprocess scraping with Celery task
This is the biggest refactor. The current flow blocks the HTTP request for up to 5 minutes.

**Prerequisites:** Add to requirements.txt: `celery>=5.3.0`, `redis>=5.0.0`

**Step 1:** Add Redis to docker-compose.yml:
```yaml
  redis:
    image: redis:7-alpine
    restart: unless-stopped
```

**Step 2:** Add to settings.py:
```python
CELERY_BROKER_URL = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
CELERY_RESULT_BACKEND = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_TIME_LIMIT = 120  # 2 min hard limit per task
```

**Step 3:** Create `helloworld/celery.py`:
```python
import os
from celery import Celery

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'helloworld.settings')
app = Celery('helloworld')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()
```

**Step 4:** Add to `helloworld/__init__.py`:
```python
from .celery import app as celery_app
__all__ = ('celery_app',)
```

**Step 5:** Create `hello/tasks.py`:
```python
from celery import shared_task
import subprocess, json, os, logging
from django.conf import settings

logger = logging.getLogger(__name__)

@shared_task(bind=True, max_retries=2, default_retry_delay=10)
def scrape_and_create_listing(self, airbnb_url, host_profile_id, description, co_host_requirements):
    from .models import HostProfile, MarketplaceListing
    try:
        script_path = os.path.join(settings.BASE_DIR, 'standalone_scraper.py')
        result = subprocess.run(
            ['python', script_path, airbnb_url],
            capture_output=True, text=True, timeout=90
        )
        if result.returncode != 0:
            raise Exception(f"Scraper failed: {result.stderr[:500]}")
        data = json.loads(result.stdout)
        host_profile = HostProfile.objects.get(pk=host_profile_id)
        listing = MarketplaceListing.objects.create(
            host=host_profile,
            title=data.get('title', 'Untitled'),
            location=data.get('location', ''),
            airbnb_url=airbnb_url,
            main_photo_url=data.get('main_photo_url', ''),
            main_photo_path=data.get('main_photo_path', ''),
            description=description,
            co_host_requirements=co_host_requirements,
            property_type=data.get('property_type', ''),
            guests_capacity=data.get('guests_capacity', ''),
            bedrooms=data.get('bedrooms', ''),
            bathrooms=data.get('bathrooms', ''),
            original_host_name=data.get('host_name', ''),
            original_host_id=data.get('host_id', ''),
            original_host_photo_url=data.get('host_photo_url', ''),
            original_host_photo_path=data.get('host_photo_path', ''),
        )
        host_profile.total_listings = host_profile.marketplace_listings.count()
        host_profile.save()
        return {'status': 'success', 'listing_id': listing.pk}
    except Exception as exc:
        logger.exception("Scrape task failed for URL %s", airbnb_url)
        raise self.retry(exc=exc)
```

**Step 6:** In `add_listing` view, replace the `subprocess.run(...)` block with:
```python
from .tasks import scrape_and_create_listing
task = scrape_and_create_listing.delay(
    airbnb_url,
    host_profile.pk,
    form.cleaned_data['description'],
    form.cleaned_data['co_host_requirements'],
)
messages.success(request, 'Your listing is being added — it will appear in your dashboard within a minute.')
return redirect('host_dashboard')
```

**Step 7:** Add a `scraping_status` field to `MarketplaceListing` model (`pending|ready|failed`) and poll from the dashboard via a small AJAX endpoint so users see a spinner while scraping.

---

## PHASE 7 — Basic Test Suite (1 session)

### TASK 7.1 — Create test structure
**Create:** `hello/tests/__init__.py` (empty)

**Create:** `hello/tests/test_views.py`:
```python
from django.test import TestCase, Client
from django.contrib.auth.models import User
from hello.models import UserProfile, HostProfile, CoHostProfile

class MarketplaceHomeTest(TestCase):
    def test_homepage_loads(self):
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)

class AuthFlowTest(TestCase):
    def test_register_host(self):
        response = self.client.post('/register/', {
            'username': 'testhost', 'password1': 'Testpass123!',
            'password2': 'Testpass123!', 'first_name': 'Test', 'last_name': 'Host',
            'email': 'test@example.com', 'role': 'host',
        })
        self.assertEqual(User.objects.filter(username='testhost').count(), 1)

    def test_host_dashboard_requires_login(self):
        response = self.client.get('/host/dashboard/')
        self.assertRedirects(response, '/login/?next=/host/dashboard/')

class AddListingPermissionTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('cohost_user', password='pass')
        self.profile = UserProfile.objects.create(user=self.user, role='cohost')
        CoHostProfile.objects.create(user_profile=self.profile, locations='Paris')

    def test_cohost_cannot_access_add_listing(self):
        self.client.login(username='cohost_user', password='pass')
        response = self.client.get('/host/add-listing/')
        self.assertNotEqual(response.status_code, 200)
```

**Run tests:**
```bash
python manage.py test hello.tests
```

---

## Execution Checklist

### Deploy to Production Sequence:
```
[ ] Phase 1 complete (secrets, CSRF, headers, static files, requirements.txt)
[ ] Phase 2 complete (logging, Sentry, error pages)
[ ] Phase 3 complete (indexes, N+1 fixes, upload validation, SSRF protection)
[ ] Task 4.2 done (email config)
[ ] Task 4.1 done (password reset)
[ ] Task 4.3 done (admin registered)
[ ] Task 5.1 done (gunicorn config)
[ ] Task 5.2 done (Dockerfile)
[ ] Task 5.3 done (docker-compose)
[ ] python manage.py collectstatic
[ ] python manage.py migrate
[ ] python manage.py createsuperuser
[ ] Test login → host flow → add listing end-to-end
[ ] Verify media uploads work
[ ] Verify email sends (password reset)
```

### Quick Wins Order (if doing tasks one at a time):
1. TASK 1.1 (secrets) + TASK 1.3 (remove prints) — 15 min
2. TASK 1.2 (csrf_exempt) — 5 min
3. TASK 1.4 (security headers) — 5 min
4. TASK 1.5 (static files + whitenoise) — 10 min
5. TASK 1.6 (requirements.txt) — 5 min
6. TASK 2.1 (logging) — 10 min
7. TASK 2.3 (sentry) — 5 min
8. TASK 4.2 (email) + TASK 4.1 (password reset) — 30 min
9. TASK 4.3 (admin) — 10 min
10. TASK 3.1 (indexes) — 10 min
11. TASK 3.3 (upload validation) + TASK 3.4 (SSRF) — 15 min
