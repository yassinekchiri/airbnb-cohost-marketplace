# Project status

Last updated: 2026-11-22. **Update this file at the end of every working session.**
Why things are the way they are: `docs/DECISIONS.md`.

## Done
- Application: Django 5.2 LTS marketplace; `pytest` (47 tests) and `ruff` green.
- CI (`.github/workflows/ci.yml`) green on `master`: lint (ruff, actionlint + shellcheck), tests on SQLite and Postgres,
  migrations in sync, `check --deploy`, pip-audit, gitleaks, image build, Trivy, full-stack smoke. Aggregate check: `CI / ci-ok`.
- `master` is protected by a ruleset requiring a PR and `CI / ci-ok` (set up by the owner).
- Workflows `deploy.yml`, `nightly.yml`, `lab.yml` are installed but have never run a real deploy.
- Dependabot configured: Django stays on 5.2 LTS, Docker base image stays on Python 3.12, Actions updates grouped.
  The Python minor/patch group (#8) is merged. #4 (trivy-action), #5 (Python 3.15 image) and #10 (Django 6) were closed on purpose.
- Proxmox installed on the NUC by the owner (node `myproxmox`, 192.168.1.101, template 9000, storage `lab-thin`, NFS storage `nas`).
  The "control" VM 200 (192.168.1.200) was made by hand and runs the GitHub runner (label `nuc`).
- `infra/nuc/terraform/` (provider `bpg/proxmox`): disposable "lab" VM 210 (192.168.1.210), cloud-init Docker + Tailscale,
  state and cloud-init snippets on the NAS. Workflow `nuc-terraform.yml`: validate + plan on PRs, apply on merge, manual destroy/apply.
- `lab.yml` and the staging job of `deploy.yml` target the control runner; their smoke test runs on the VM's host network
  (works whether the runner is a container or native).

## Verified on master
- The `publish signed image` job runs on every `master` push: it builds, pushes to GHCR and signs the digest with cosign (keyless). Confirmed green on the run for commit `1ae41ca`.
- `deploy.yml` used to queue on every merge, waiting for a NUC runner that does not exist (runs were cancelled after about a day).
  It is now gated by the repository variable `DEPLOY_ENABLED` (off by default).

## Not verified
- `infra/proxmox/host-setup.sh` end to end (the owner set up Proxmox; which steps of the script were used is unknown).
- `infra/nuc/terraform/` apply (never run). Verified on the PR (2026-11-22): `validate` green, and `plan` on the NUC runner
  against the real node reads the NAS state and shows `2 to add, 0 to change, 0 to destroy` (snippet + VM 210).
- `lab.yml` and the staging job on the control runner (never run).
- The deploy, rollback and verify steps of `deploy.yml` (never run; needs a runner, a VM and secrets).

## Blocked on the owner
| Item | Detail |
|---|---|
| GitHub environments | create `staging` (no rules) and `production` (required reviewer = owner, branch `master`) |
| GitHub code security | Dependabot alerts + security updates, secret scanning, push protection (private repo: may need a paid plan) |
| Install Proxmox on the NUC | follow `docs/PROXMOX.md`; wipes ESXi |
| NUC Terraform prerequisites | NAS: NFS read/write for 192.168.1.200 on `/volume1/CoHostBackup`; Proxmox: content **Snippets** on storage `nas`; run `infra/nuc/control-nas-mount.sh` as root on VM 200; keep .200-.220 out of DHCP (details: `infra/nuc/terraform/README.md`) |
| NUC Terraform secrets | repository secret `PROXMOX_VE_API_TOKEN` (`terraform@pve!provider=<uuid>`); optional secret `NUC_LAB_TAILSCALE_AUTHKEY`, optional variable `NUC_LAB_SSH_AUTHORIZED_KEYS` |
| Cloud provider and domain | Hetzner vs Scaleway undecided; domain not chosen |
| Deploy switch | when runner + VM + secrets exist, set the repository variable `DEPLOY_ENABLED=true` (Settings > Secrets and variables > Actions > Variables) |
| Accounts and secrets | cloud, Cloudflare, Tailscale (tag `tag:ci`, OAuth client), SMTP provider, Sentry, uptime monitor; production secrets listed in `docs/CICD.md` section 2 |
| Legal | CNDP declaration (Law 09-08) and a local lawyer's view on hosting abroad |

## Next steps for Claude (in order)
1. Triage the open Dependabot PRs #2, #3, #6, #7, #9, #11, #12: ask Dependabot to rebase, merge those with green CI.
   Treat `gunicorn` (#9) and `redis` (#12) with care (production-facing); read their release notes first.
2. (done) Signed image publishing verified; deploys gated behind `DEPLOY_ENABLED`.
3. (done, unverified) `infra/nuc/terraform/` for the "lab" VM; `lab.yml` and staging wired to the control runner.
   `validate` passed against the real provider (bpg/proxmox 0.123.1, lock file committed). Owner prerequisites done, PR plan verified.
   Next: merge (runs `apply`, creates VM 210), check cloud-init on the VM, then run `lab.yml` once.
4. Rebuild drill: Actions > NUC Terraform > `destroy` then `apply`, restore the latest `pg_dump` from the NAS.
   Optional: move the lab/staging compose stacks from the control VM onto the lab VM (isolates the runner host from branch code).
5. After provider and domain are chosen: Terraform for the cloud VM, buckets and DNS, then the first production deploy.

## Open product work
Celery async scraping + isolated scraper image (Phase 6); media to object storage (django-storages);
Arabic/French i18n + RTL; Playwright E2E.
