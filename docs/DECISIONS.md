# Decision log

One row per decision. Do not re-open a settled one without a new reason; add a row when you change it.
Status: **settled**, **open** (needs the owner) or **superseded**.

| Date | Decision | Why | Status |
|---|---|---|---|
| 2026-11 | CI/CD runs on **GitHub Actions**, not Jenkins | No server to maintain, workflows live in Git (rebuild everything from Git), already written | settled |
| 2026-11 | Required check is the single aggregate `CI / ci-ok`, on GitHub-hosted runners | A powered-off NUC must never block a merge | settled |
| 2026-11 | NUC hypervisor is **Proxmox VE**, replacing ESXi | Free ESXi licence makes the API read-only, so Terraform cannot create or destroy VMs | settled |
| 2026-11 | NUC lab is disposable: rebuilt from Git + the NAS. VM disks hold no state | Goal of the lab: break and redeploy at will | settled |
| 2026-11 | NAS (NFS) holds backups (`vzdump`, `pg_dump`), ISOs, cloud-init snippets, lab Terraform state. **Not** the live Postgres data directory | NFS and fsync/locking are a bad fit for a database | settled |
| 2026-11 | Terraform for the NUC runs on a self-hosted runner in a long-lived "control" guest; cloud Terraform runs on GitHub-hosted runners | The Proxmox API is only reachable on the LAN; the runner must not live in a VM it rebuilds | settled |
| 2026-11 | Trivy runs from the official `aquasec/trivy` image, not `aquasecurity/trivy-action` | The action's `setup-trivy` dependency could not be resolved | settled |
| 2026-11 | Trivy skips `pip/_vendor/bom.cdx.json` only | pip's vendored SBOM lists `setuptools 70.3.0` (false positive CVE-2025-47273); the real setuptools is >= 78.1.1. Installed packages are still scanned | settled |
| 2026-11 | Stay on **Django 5.2 LTS** and **Python 3.12** base image; Dependabot ignores the bumps | A major upgrade is a deliberate project, not a bot PR | settled |
| 2026-11 | Production = one EU VM behind Cloudflare, Caddy for TLS, Docker Compose, Tailscale for SSH | Cheapest option that fits; managed services can come later (change `DATABASE_URL`) | settled |
| 2026-11 | Moroccan hosting only if the CNDP, a customer contract or latency data requires it | Higher price, no API/Terraform, no S3-compatible storage | settled |
| 2026-11 | Secrets are files (`NAME_FILE`), never env vars or Git; SOPS + age for any copy in Git | See `docs/ARCHITECTURE.md` section 5 | settled |
| - | **Cloud provider**: Hetzner Cloud (cheaper, about 60-80 ms to Morocco) vs Scaleway Paris (about 40-60 ms, managed Postgres, higher price) | Leaning Hetzner on cost | **open** |
| - | **Domain name** | Not chosen yet | **open** |
| - | Proxmox storage: ext4 vs ZFS | Depends on the NUC's RAM and the owner's wish for ZFS snapshots | **open** |

## How to read the numbers
Prices and latencies were estimated from memory when the decisions were made. Check the providers' pricing pages before committing.
