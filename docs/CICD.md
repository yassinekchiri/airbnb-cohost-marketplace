# CI/CD runbook

Everything runs on GitHub (Actions + GHCR) plus the home NUC for staging. No laptop is involved:
code is written in Claude Code on the web, merged and approved from a browser or the GitHub mobile app.

```
branch claude/*  ->  PR  ->  CI (GitHub-hosted, required)  ->  merge to master
                                                                   |
                                    build + sign image (GHCR, cosign) <- same CI run
                                                                   |
                        Deploy workflow: verify signature -> NUC staging -> [approval] -> production
```

## What blocks a merge (and what never does)
Branch protection requires **one** check: `CI / ci-ok`. It aggregates lint, tests (SQLite + Postgres),
migrations-in-sync, `check --deploy`, pip-audit, gitleaks, image build + Trivy, and a full-stack smoke test.
All of it runs on GitHub-hosted runners, so **a powered-off NUC can never block a merge**.
The NUC only gates *staging*, and that gate has a manual bypass (below).

| Workflow | Trigger | Runs on | Purpose |
|---|---|---|---|
| `ci.yml` | PR, push to master | GitHub | quality gate; on master also publishes + signs the image |
| `deploy.yml` | CI success on master, or manual | GitHub + NUC | verify signature, NUC staging, approval, production, auto-rollback |
| `nightly.yml` | 03:17 UTC | GitHub | new CVEs in dependencies / the published image |
| `lab.yml` | manual | NUC | build any branch on the NUC, run the full stack + smoke |

## One-time setup (about 30 minutes, all doable in a browser)

### 0. Workflows (done)
The four workflow files live in **`.github/workflows/`**. The Claude GitHub App has the *Workflows: read and write*
permission, so Claude can change them through a normal PR. Trivy runs from its official image (`aquasec/trivy`)
instead of `trivy-action`, whose internal `setup-trivy` dependency could not be resolved.

### 1. GitHub repo settings
- **Branches**: protect `master`: require a PR, require status check `CI / ci-ok`, block force pushes.
- **Actions > General**: default workflow permissions = *Read*; require approval for outside collaborators.
- **Environments**: create `staging` (no rules) and `production` (**Required reviewers** = you; deployment branches = `master`).
- Enable **Secret scanning + push protection** and **Dependabot alerts** (Settings > Code security).

### 2. Production environment secrets / variables
| Kind | Name | Value |
|---|---|---|
| var | `SITE_URL` | `https://cohost.example.ma` |
| var | `SITE_DOMAIN` | `cohost.example.ma` |
| var | `ACME_EMAIL` | email for Let's Encrypt notices |
| var | `DEPLOY_HOST` | the VM's tailnet name, e.g. `cohost-prod` |
| var | `DEPLOY_HOST_KEY` | printed at the end of `server-bootstrap.sh` (`ssh-ed25519 AAAA...`) |
| secret | `DEPLOY_SSH_KEY` | private half of a **new** ed25519 key used only for deploys |
| secret | `TS_OAUTH_CLIENT_ID`, `TS_OAUTH_SECRET` | Tailscale OAuth client (scope: auth keys, tag `tag:ci`) |
| secret | `EMAIL_HOST_PASSWORD`, `SENTRY_DSN` | pushed to the server's `secrets/` on each deploy |

Generated secrets (`SECRET_KEY`, DB and Redis passwords) are created **on the server** by `setup.sh secrets`
on first deploy and never leave it.

### 3. Tailscale
Create a tailnet; add ACL tag `tag:ci`; allow `tag:ci` -> `cohost-prod:22`. Create an OAuth client with the
`auth_keys` write scope for `tag:ci`. Production SSH is reachable **only** through the tailnet.

### 4. Production VM
Create an Ubuntu 24.04 VM (see ARCHITECTURE.md section 7), then as root:
`DEPLOY_PUBKEY="ssh-ed25519 ... " TS_AUTHKEY=tskey-auth-... bash deploy/server-bootstrap.sh`
It installs Docker + Tailscale, creates the `deploy` user, locks SSH to the tailnet, opens only 80/443.
Point DNS (Cloudflare) at the VM, then run **Deploy** once. The first run generates secrets and starts everything.

### 5. NUC (optional, test only)
Install Proxmox first (`docs/PROXMOX.md`), then in an Ubuntu VM on it: `GITHUB_REPO=owner/repo RUNNER_PAT=github_pat_... bash infra/nuc/bootstrap-runner-vm.sh`.
The PAT is a fine-grained token with *Administration: read/write* on this one repository. Put the VM on an isolated VLAN.

## Day-to-day
- **Ship**: merge the PR. CI publishes the image; Deploy runs staging, then waits for your approval (GitHub mobile push notification).
- **Roll back**: Actions > Deploy > Run workflow > `image_tag` = an older commit SHA. Or, on failure, it rolls back by itself.
- **NUC offline**: Run workflow with `skip_staging` ticked. (A deploy waiting on a dead runner just queues.)
- **Try a branch on the full stack**: Actions > NUC lab.

## Failure behaviour
| Failure | What happens |
|---|---|
| Tests/lint/audit fail | merge blocked |
| New CVE in a dependency | nightly fails; Dependabot opens a PR |
| Image not signed by `ci.yml` on master | `resolve` job refuses to deploy |
| Staging smoke fails | production job never starts |
| Migration fails | old image keeps serving; deploy fails |
| New web container unhealthy | script restores the previous image automatically |
| Public smoke fails after deploy | workflow rolls back and fails |

Migrations must be **additive** (add nullable columns/tables; remove or rename in a later release), because
rollback swaps the image back without reverting the database.

## Known limits
- Swap is near-zero-downtime (Caddy retries the upstream for up to 20 s), not blue/green.
- First prod deploy cannot be tested until a VM exists; staging/CI paths use the same compose and smoke test.
- Actions are pinned to major tags; Dependabot keeps them current. Pin to commit SHAs if you want stricter supply-chain control.
