from django.urls import reverse


def test_host_accepts_proposal_marks_listing_found(client, host, proposal, login):
    login(host)
    r = client.post(reverse("accept_proposal", args=[proposal.id]))
    proposal.refresh_from_db()
    proposal.listing.refresh_from_db()
    assert r.status_code == 302
    assert proposal.status == "accepted"
    assert proposal.listing.status == "found"


def test_host_declines_proposal(client, host, proposal, login):
    login(host)
    client.post(reverse("decline_proposal", args=[proposal.id]))
    proposal.refresh_from_db()
    assert proposal.status == "declined"


def test_one_proposal_per_cohost_per_listing(db, proposal):
    import pytest
    from django.db import IntegrityError, transaction
    from hello.models import Proposal
    with pytest.raises(IntegrityError), transaction.atomic():
        Proposal.objects.create(listing=proposal.listing, cohost=proposal.cohost, message="again")
