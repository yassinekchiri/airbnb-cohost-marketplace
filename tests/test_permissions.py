from django.urls import reverse



def test_cohost_cannot_open_host_dashboard(client, cohost, login):
    login(cohost)
    r = client.get(reverse("host_dashboard"))
    assert r.status_code == 302 and r["Location"] == reverse("marketplace_home")


def test_host_cannot_open_cohost_dashboard(client, host, login):
    login(host)
    r = client.get(reverse("cohost_dashboard"))
    assert r.status_code == 302


def test_host_sees_own_dashboard(client, host, listing, login):
    login(host)
    r = client.get(reverse("host_dashboard"))
    assert r.status_code == 200 and b"Riad in Marrakech" in r.content


def test_other_host_cannot_accept_proposal(client, other_host, proposal, login):
    login(other_host)
    r = client.post(reverse("accept_proposal", args=[proposal.id]))
    proposal.refresh_from_db()
    assert r.status_code == 302 and proposal.status == "pending"


def test_cohost_cannot_accept_own_proposal(client, cohost, proposal, login):
    login(cohost)
    client.post(reverse("accept_proposal", args=[proposal.id]))
    proposal.refresh_from_db()
    assert proposal.status == "pending"


def test_accept_requires_post(client, host, proposal, login):
    login(host)
    client.get(reverse("accept_proposal", args=[proposal.id]))
    proposal.refresh_from_db()
    assert proposal.status == "pending"


def test_non_participant_cannot_read_conversation(client, other_host, proposal, login):
    login(other_host)
    r = client.get(reverse("conversation", args=[proposal.id]))
    assert r.status_code in (302, 403, 404)
    assert b"I manage 12 riads" not in r.content


def test_admin_requires_staff(client, host, login):
    login(host)
    r = client.get("/admin/")
    assert r.status_code == 302 and "/admin/login/" in r["Location"]
