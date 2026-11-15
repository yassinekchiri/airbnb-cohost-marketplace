import pytest
from django.urls import reverse

PUBLIC = ["marketplace_home", "listings_marketplace", "cohosts_marketplace",
          "privacy_policy", "terms_of_service", "contact", "login", "register", "password_reset"]


def test_healthz_ok_and_checks_database(client, db):
    r = client.get("/healthz")
    assert r.status_code == 200 and r.content == b"ok"


@pytest.mark.parametrize("name", PUBLIC)
def test_public_pages_render(client, db, name):
    assert client.get(reverse(name)).status_code == 200


def test_unknown_url_uses_custom_404(client, db):
    assert client.get("/no-such-page/").status_code == 404


@pytest.mark.parametrize("name", ["host_dashboard", "cohost_dashboard", "inbox", "edit_profile", "add_listing"])
def test_private_pages_redirect_anonymous_to_login(client, db, name):
    r = client.get(reverse(name))
    assert r.status_code == 302 and r["Location"].startswith("/login/")
