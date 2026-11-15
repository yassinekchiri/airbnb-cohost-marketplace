import os

os.environ.setdefault("SECRET_KEY", "test-only-secret-key-not-for-production")
os.environ.setdefault("DEBUG", "False")
os.environ.setdefault("ALLOWED_HOSTS", "testserver,localhost")
os.environ.setdefault("LOG_TO_FILE", "False")

import pytest
from django.contrib.auth.models import User

from hello.models import CoHostProfile, HostProfile, MarketplaceListing, Proposal, UserProfile


@pytest.fixture(autouse=True)
def _isolate_settings(settings):
    """Keep tests hermetic: no Redis, no cache table, no manifest, no SMTP, no TLS redirect."""
    settings.CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}
    settings.STORAGES = {
        "default": {"BACKEND": "django.core.files.storage.InMemoryStorage"},
        "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
    }
    settings.EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
    settings.SECURE_SSL_REDIRECT = False
    settings.PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]  # fast


PASSWORD = "S3cure-pass-for-tests!"


def _make_user(username, role):
    user = User.objects.create_user(username, f"{username}@example.com", PASSWORD,
                                    first_name=username.title(), last_name="Test")
    profile = UserProfile.objects.create(user=user, role=role)
    if role == "host":
        HostProfile.objects.create(user_profile=profile)
    else:
        CoHostProfile.objects.create(user_profile=profile, locations="Casablanca")
    return user


@pytest.fixture
def host(db):
    return _make_user("hostanna", "host")


@pytest.fixture
def other_host(db):
    return _make_user("hostbob", "host")


@pytest.fixture
def cohost(db):
    return _make_user("cohostyoussef", "cohost")


@pytest.fixture
def listing(host):
    return MarketplaceListing.objects.create(
        host=host.userprofile.hostprofile,
        title="Riad in Marrakech",
        location="Marrakech",
        platform="other",
        description="Quiet riad near the medina.",
        co_host_requirements="Arabic and French.",
    )


@pytest.fixture
def proposal(listing, cohost):
    return Proposal.objects.create(
        listing=listing, cohost=cohost.userprofile.cohostprofile,
        message="I manage 12 riads in Marrakech.",
    )


@pytest.fixture
def login(client):
    def _login(user):
        assert client.login(username=user.username, password=PASSWORD)
        return client
    return _login
