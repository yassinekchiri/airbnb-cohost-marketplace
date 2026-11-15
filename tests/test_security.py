import pytest
from django.core.management import call_command

from hello.views import _validate_scraper_url


@pytest.mark.parametrize("url", [
    "https://www.airbnb.com/rooms/12345",
    "https://airbnb.com/rooms/12345?x=1",
    "http://fr.airbnb.com/rooms/1",
])
def test_scraper_accepts_airbnb_urls(url):
    _validate_scraper_url(url)


@pytest.mark.parametrize("url", [
    "ftp://airbnb.com/rooms/1",
    "https://example.com/rooms/1",
    "https://127.0.0.1/airbnb.com",
    "https://169.254.169.254/latest/meta-data/?airbnb.com",
    "https://airbnb.com.evil.example/rooms/1",        # lookalike suffix
    "https://evil.example/airbnb.com",                # path trick
    "https://evil-airbnb.com/rooms/1",                # prefix lookalike
    "https://airbnb.com@evil.example/rooms/1",        # userinfo trick
])
def test_scraper_rejects_ssrf_and_lookalikes(url):
    with pytest.raises(ValueError):
        _validate_scraper_url(url)


@pytest.mark.django_db
def test_no_missing_migrations():
    call_command("makemigrations", "--check", "--dry-run")


def test_security_headers_present(client, db):
    r = client.get("/")
    assert r["X-Content-Type-Options"] == "nosniff"
    assert r["X-Frame-Options"] == "DENY"
