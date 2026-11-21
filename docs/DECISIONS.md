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
| 2026-11 | Deploys are off until the repository variable `DEPLOY_ENABLED` is `true` | Without a runner and VM every merge queued a deploy that waited for a runner that does not exist; a stale deploy could also start when a runner is registered later | settled |
| 2026-11 | Secrets are files (`NAME_FILE`), never env vars or Git; SOPS + age for any copy in Git | See `docs/ARCHITECTURE.md` section 5 | settled |
| 2026-11 | NUC lab facts: node `myproxmox`, Proxmox IP 192.168.1.101, gateway 192.168.1.254, VM IP range 192.168.1.200-220. `control` = VM 200 at 192.168.1.200, `lab` = VM 210 at 192.168.1.210. Do not touch VM 101 or template 9000 | Real values of the NUC lab; Terraform uses them | settled |
| 2026-11 | Storage: OS disk (256 GB SSD, ext4) holds `local` and `local-lvm`. VM disks go on `lab-thin` (LVM-thin, 1 TB SSD), not on `local-lvm` | The `local-lvm` thin pool is small and overcommitted | settled |
| 2026-11 | NFS storage `nas` = 192.168.1.15:/volume1/CoHostBackup, mounted as NFS v3 because NFS v4.1 is not enabled on the NAS. It holds backups, ISOs, snippets and the lab Terraform state. An unrelated NFS storage `OS` also exists on the host; CoHost does not use it | Matches what the NAS supports today | settled |
| 2026-11 | `control` is created by hand once (clone of template 9000); everything else goes through the pipeline | Chicken-and-egg: the runner that runs Terraform must exist first | settled |
| - | **Cloud provider**: Hetzner Cloud (cheaper, about 60-80 ms to Morocco) vs Scaleway Paris (about 40-60 ms, managed Postgres, higher price) | Leaning Hetzner on cost | **open** |
| - | **Domain name** | Not chosen yet | **open** |
| - | Proxmox storage: ext4 vs ZFS | Depends on the NUC's RAM and the owner's wish for ZFS snapshots | **open** |

## How to read the numbers
Prices and latencies were estimated from memory when the decisions were made. Check the providers' pricing pages before committing.
