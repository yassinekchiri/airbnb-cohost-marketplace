# Project status

Last updated: 2026-11-21. **Update this file at the end of every working session.**
Why things are the way they are: `docs/DECISIONS.md`.

## Done
- Application: Django 5.2 LTS marketplace; `pytest` (47 tests) and `ruff` green.
- CI (`.github/workflows/ci.yml`) green on `master`: lint (ruff, actionlint + shellcheck), tests on SQLite and Postgres,
  migrations in sync, `check --deploy`, pip-audit, gitleaks, image build, Trivy, full-stack smoke. Aggregate check: `CI / ci-ok`.
- `master` is protected by a ruleset requiring a PR and `CI / ci-ok` (set up by the owner).
- Workflows `deploy.yml`, `nightly.yml`, `lab.yml` are installed but have never run a real deploy.
- Dependabot configured: Django stays on 5.2 LTS, Docker base image stays on Python 3.12, Actions updates grouped.
  The Python minor/patch group (#8) is merged. #4 (trivy-action), #5 (Python 3.15 image) and #10 (Django 6) were closed on purpose.
- Proxmox runbook and host script written (`docs/PROXMOX.md`, `infra/proxmox/host-setup.sh`) and run on the real host (bugs found: see Not verified).
- Proxmox VE 9.2 (Debian trixie) is installed on the NUC, replacing ESXi.
- Host steps run on the real host: `repos`, `template` (template 9000 `ubuntu-2404-cloud` exists) and `terraform`
  (API token created and stored in the owner's password manager; never in Git).
- NFS storage `nas` was added by hand (the `nfs` step failed on this NAS, see below and `docs/DECISIONS.md`).
- A second 1 TB SSD was added as LVM-thin storage `lab-thin`.
- The old ESXi VM `cohost` was imported as VM 102 `cohost-2` and boots. VM 100 (failed first import) was destroyed.

## Verified on master
- The `publish signed image` job runs on every `master` push: it builds, pushes to GHCR and signs the digest with cosign (keyless). Confirmed green on the run for commit `1ae41ca`.
- `deploy.yml` used to queue on every merge, waiting for a NUC runner that does not exist (runs were cancelled after about a day).
  It is now gated by the repository variable `DEPLOY_ENABLED` (off by default).

## Not verified
- `infra/proxmox/host-setup.sh`: `repos`, `template` and `terraform` ran on the real host with the bugs listed in `docs/PROXMOX.md` ("Lessons from the first real install"); the `nfs` step failed on this NAS (no NFS v4.1). The script fixes for these have not been re-run on the host.
- The deploy, rollback and verify steps of `deploy.yml` (never run; needs a runner, a VM and secrets).

## Blocked on the owner
| Item | Detail |
|---|---|
| GitHub environments | create `staging` (no rules) and `production` (required reviewer = owner, branch `master`) |
| GitHub code security | Dependabot alerts + security updates, secret scanning, push protection (private repo: may need a paid plan) |
| Control VM 200 | create by hand (clone of template 9000), run `infra/nuc/bootstrap-runner-vm.sh` on it, add the Proxmox API token as a GitHub secret |
| Cloud provider and domain | Hetzner vs Scaleway undecided; domain not chosen |
| Deploy switch | when runner + VM + secrets exist, set the repository variable `DEPLOY_ENABLED=true` (Settings > Secrets and variables > Actions > Variables) |
| Accounts and secrets | cloud, Cloudflare, Tailscale (tag `tag:ci`, OAuth client), SMTP provider, Sentry, uptime monitor; production secrets listed in `docs/CICD.md` section 2 |
| Legal | CNDP declaration (Law 09-08) and a local lawyer's view on hosting abroad |

## Next steps for Claude (in order)
1. Triage the open Dependabot PRs #2, #3, #6, #7, #9, #11, #12: ask Dependabot to rebase, merge those with green CI.
   Treat `gunicorn` (#9) and `redis` (#12) with care (production-facing); read their release notes first.
2. (done) Signed image publishing verified; deploys gated behind `DEPLOY_ENABLED`.
3. Write `infra/nuc/terraform/` using the facts in `docs/DECISIONS.md` (node, IPs, storages) (provider `bpg/proxmox`, "lab" and "control" guests from template 9000,
   cloud-init with Docker, Tailscale and the runner, state on the NAS), then wire `lab.yml` and the staging job to the new runner.
4. Rebuild drill: `terraform destroy` then `apply`, restore the latest `pg_dump` from the NAS.
5. After provider and domain are chosen: Terraform for the cloud VM, buckets and DNS, then the first production deploy.

## Open product work
Celery async scraping + isolated scraper image (Phase 6); media to object storage (django-storages);
Arabic/French i18n + RTL; Playwright E2E.
