# Proxmox VE on the Intel NUC (lab hypervisor)

Why Proxmox and not ESXi: the free ESXi licence makes the API read-only, so Terraform cannot create or destroy
VMs. Proxmox VE is free with a full API, cloud-init templates, snapshots and native NFS. Goal: the NUC can be
wiped and rebuilt from **Git + the NAS** at any time (see `docs/CICD.md`).

```
NUC (Proxmox VE)
 ├─ template 9000  Ubuntu 24.04 cloud-init   <- infra/proxmox/host-setup.sh template
 ├─ LXC/VM "control"  GitHub runner (label nuc) + Terraform   <- next step, Terraform
 └─ VM "lab"          docker compose stack under test          <- next step, Terraform
NAS (NFS)  backups (vzdump, pg_dump), ISOs, cloud-init snippets, Terraform state of the lab
```

## 0. Before you wipe ESXi
Wiping the disk destroys every VM on the ESXi datastore. Export or copy anything you want to keep (OVF export,
or copy the files to the NAS). Everything that matters for CoHost is in Git, so a lab VM is disposable.

## 1. Prepare the installer (any PC, 5 minutes)
1. Download the **Proxmox VE ISO** from https://www.proxmox.com/en/downloads and verify its SHA256 (shown on that page).
2. Write it to a USB stick with Rufus (DD mode) or balenaEtcher.
3. NUC BIOS (F2 at boot): enable **Intel VT-x / VT-d**, boot from USB. Secure Boot may stay on (current Proxmox supports it).

## 2. Install (graphical installer)
| Screen | Choice |
|---|---|
| Target disk | One SSD/NVMe. **ext4** is simplest. Pick **ZFS (RAID0)** only if the NUC has 16 GB RAM or more and you want ZFS snapshots; then use `STORAGE=local-zfs` below |
| Country / time zone | Morocco, `Africa/Casablanca` |
| Password / e-mail | Strong root password (password manager), a real e-mail for alerts |
| Network | **Static IP** on your LAN, e.g. `192.168.1.10/24`, gateway = router, DNS = router or 1.1.1.1. Hostname FQDN e.g. `pve.lab.local` |

Reboot, remove the USB stick, then open `https://<ip>:8006` (accept the self-signed certificate) and log in as
`root` (realm *Linux PAM*). Dismiss the "no valid subscription" notice; it is cosmetic.

## 3. NAS export (NFS)
Create one shared folder, e.g. `proxmox`, and export it over **NFS v4.1** to the Proxmox IP only
(Synology: Control Panel > Shared Folder > NFS Permissions; squash = *Map all users to admin* or *no mapping*,
privilege *Read/Write*). Enable snapshots on that folder if the NAS supports it.

## 4. Host setup script
From the Proxmox web UI open **Shell** on the node (or SSH as root), then:
```bash
apt-get update && apt-get install -y git
git clone https://github.com/yassinekchiri/airbnb-cohost-marketplace.git && cd airbnb-cohost-marketplace
bash infra/proxmox/host-setup.sh repos                       # no-subscription repo + upgrade; reboot after
NAS_IP=192.168.1.20 NAS_EXPORT=/volume1/proxmox bash infra/proxmox/host-setup.sh nfs
bash infra/proxmox/host-setup.sh template                    # STORAGE=local-zfs if you chose ZFS
bash infra/proxmox/host-setup.sh terraform                   # prints the API token ONCE
```
Every step is idempotent. If a step fails, fix the cause and run it again.

## 5. Harden the host
- **2FA** on `root@pam`: Datacenter > Permissions > Two Factor (TOTP).
- Reachable from the LAN only. Never forward port 8006 or 22 on the router. Remote access goes through Tailscale later.
- SSH: key-only (`PasswordAuthentication no` in `/etc/ssh/sshd_config`), then `systemctl reload ssh`.
- Put the lab VMs on an isolated VLAN/bridge if the router supports it (the runner holds the Docker socket).
- Datacenter > Backup: nightly `vzdump` of the "control" guest to the `nas` storage.

## 6. What to keep, what never to share
- The Terraform **API token** printed by step 4 goes into your password manager and, later, a GitHub secret
  for the lab. **Do not paste it into chat or commit it.**
- To continue the setup, only these non-secret facts are needed: Proxmox IP and node name (Datacenter > node
  name, usually `pve`), storage names (`pvesm status`), NAS model and export path, free IP range for the VMs.

## 7. Verify
```bash
pveversion            # Proxmox VE 8.x or 9.x
pvesm status          # local, local-lvm (or local-zfs), nas  -> all "active"
qm list               # shows template 9000
```

## Next steps (done in Git, by Claude)
1. `infra/nuc/terraform/`: provider `bpg/proxmox`, VM "lab" + "control" cloned from template 9000 with cloud-init
   (Docker, Tailscale, runner registration), state stored on the NAS.
2. Wire `lab.yml` and the staging job of `deploy.yml` to the new runner.
3. Rebuild drill: `terraform destroy && terraform apply`, then restore the last `pg_dump` from the NAS.
