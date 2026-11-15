import pytest
from django.contrib.auth.models import User
from django.urls import reverse

from hello.models import CoHostProfile, HostProfile
from tests.conftest import PASSWORD


def _payload(username, role, **over):
    data = {"username": username, "first_name": "Sara", "last_name": "Alaoui", "email": f"{username}@example.com",
            "password1": PASSWORD, "password2": PASSWORD, "role": role, "phone_number": "+212600000000"}
    data.update(over)
    return data


@pytest.mark.parametrize("role,profile_model", [("host", HostProfile), ("cohost", CoHostProfile)])
def test_register_creates_role_profile(client, db, role, profile_model):
    r = client.post(reverse("register"), _payload("newuser", role))
    assert r.status_code == 302
    user = User.objects.get(username="newuser")
    assert user.userprofile.role == role
    assert profile_model.objects.filter(user_profile=user.userprofile).exists()


def test_register_rejects_weak_password(client, db):
    r = client.post(reverse("register"), _payload("weak", "host", password1="12345678", password2="12345678"))
    assert r.status_code == 200 and not User.objects.filter(username="weak").exists()


def test_register_rejects_unknown_role(client, db):
    r = client.post(reverse("register"), _payload("admin2", "superuser"))
    assert r.status_code == 200 and not User.objects.filter(username="admin2").exists()


def test_login_redirects_by_role(client, host, cohost, login):
    login(host)
    assert client.get(reverse("custom_login_redirect"))["Location"] == reverse("host_dashboard")
    client.logout()
    login(cohost)
    assert client.get(reverse("custom_login_redirect"))["Location"] == reverse("cohost_dashboard")
