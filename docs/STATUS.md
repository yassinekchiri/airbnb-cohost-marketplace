# Project status

Last updated: 2026-11-20. **Update this file at the end of every working session.**
Why things are the way they are: `docs/DECISIONS.md`.

## Done
- Application: Django 5.2 LTS marketplace; `pytest` (47 tests) and `ruff` green.
- CI (`.github/workflows/ci.yml`) green on `master`: lint (ruff, actionlint + shellcheck), tests on SQLite and Postgres,
  migrations in sync, `check --deploy`, pip-audit, gitleaks, image build, Trivy, full-stack smoke. Aggregate check: `CI / ci-ok`.
- `master` is protected by a ruleset requiring a PR and `CI / ci-ok` (set up by the owner).
- Workflows `deploy.yml`, `nightly.yml`, `lab.yml` are installed but have never run a real deploy.
- Dependabot configured: Django stays on 5.2 LTS, Docker base image stays on Python 3.12, Actions updates grouped.
  The Python minor/patch group (#8) is merged. #4 (trivy-action), #5 (Python 3.15 image) and #10 (Django 6) were closed on purpose.
- Proxmox runbook and host script written (`docs/PROXMOX.md`, `infra/proxmox/host-setup.sh`); **not yet run on a real host**.

## Not verified
- Whether the first `master` CI run published and signed the image to GHCR (`publish signed image` job).
- What `deploy.yml` did after that run. It cannot deploy anywhere yet (no NUC runner, no VM, no secrets).
- `infra/proxmox/host-setup.sh` end to end (needs a Proxmox host).

## Blocked on the owner
| Item | Detail |
|---|---|
| GitHub environments | create `staging` (no rules) and `production` (required reviewer = owner, branch `master`) |
| GitHub code security | Dependabot alerts + security updates, secret scanning, push protection (private repo: may need a paid plan) |
| Install Proxmox on the NUC | follow `docs/PROXMOX.md`; wipes ESXi |
| Facts for the Terraform lab | ext4 or ZFS, Proxmox IP and node name, NAS model and NFS export path, free IP range |
| Cloud provider and domain | Hetzner vs Scaleway undecided; domain not chosen |
| Accounts and secrets | cloud, Cloudflare, Tailscale (tag `tag:ci`, OAuth client), SMTP provider, Sentry, uptime monitor; production secrets listed in `docs/CICD.md` section 2 |
| Legal | CNDP declaration (Law 09-08) and a local lawyer's view on hosting abroad |

## Next steps for Claude (in order)
1. Triage the open Dependabot PRs #2, #3, #6, #7, #9, #11, #12: ask Dependabot to rebase, merge those with green CI.
   Treat `gunicorn` (#9) and `redis` (#12) with care (production-facing); read their release notes first.
2. Check that the `master` CI run published a signed image and see what `deploy.yml` did.
3. Once the owner gives the Proxmox facts: `infra/nuc/terraform/` (provider `bpg/proxmox`, "lab" and "control" guests from template 9000,
   cloud-init with Docker, Tailscale and the runner, state on the NAS), then wire `lab.yml` and the staging job to the new runner.
4. Rebuild drill: `terraform destroy` then `apply`, restore the latest `pg_dump` from the NAS.
5. After provider and domain are chosen: Terraform for the cloud VM, buckets and DNS, then the first production deploy.

## Open product work
Celery async scraping + isolated scraper image (Phase 6); media to object storage (django-storages);
Arabic/French i18n + RTL; Playwright E2E.
