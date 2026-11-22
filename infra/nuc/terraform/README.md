# NUC lab Terraform (Proxmox, provider `bpg/proxmox`)

Manages **one** disposable VM on node `myproxmox` (https://192.168.1.101:8006/):

| Guest | Id | IP | Managed here | Notes |
|---|---|---|---|---|
| `lab` | 210 | 192.168.1.210/24 | yes | full clone of template 9000 on `lab-thin`, 2 vCPU, 4 GB, 40 GB; cloud-init installs Docker + Tailscale |
| `control` | 200 | 192.168.1.200/24 | **no** | made by hand; runs the GitHub runner (label `nuc`) and this Terraform |
| 100, 101, 102, template 9000 | | | **no** | the template is only read by the clone; a precondition refuses these ids |

State: `nas:/terraform/nuc-lab/terraform.tfstate`, i.e. `192.168.1.15:/volume1/CoHostBackup/terraform/nuc-lab/`.
Cloud-init user-data: written by Terraform to `/volume1/CoHostBackup/snippets/`, which Proxmox sees as `nas:snippets/...`.
That is why the only Proxmox credential is the API token (no SSH to the node).

## How it runs
Workflow `.github/workflows/nuc-terraform.yml`, all on the NUC runner except `validate`:

| Event | Jobs |
|---|---|
| PR touching `infra/nuc/terraform/**` | `validate` (GitHub-hosted: fmt, validate) + `plan` (NUC); plan is in the job summary |
| merge to `master` | `validate` + `apply` |
| Actions > NUC Terraform > Run workflow | `plan`, or on `master` `apply` / `destroy` |

`tf.sh` runs `hashicorp/terraform` in a container on the control VM's Docker daemon, with the NAS
sub-directories bind-mounted. It refuses to run if the NAS is not mounted (marker file on the share),
so state can never land on the VM's local disk.

## GitHub settings (owner)
| Kind | Name | Value | Required |
|---|---|---|---|
| repository **secret** | `PROXMOX_VE_API_TOKEN` | `terraform@pve!provider=<token secret>`: the full id, `=`, then the UUID printed once by `host-setup.sh terraform` | yes |
| repository **secret** | `NUC_LAB_TAILSCALE_AUTHKEY` | Tailscale auth key: reusable, pre-approved, tagged (e.g. `tag:lab`), **not** ephemeral (see "Tailscale" below) | no: without it Tailscale is installed but not joined |
| repository **variable** (Variables tab, **not** Secrets) | `NUC_LAB_SSH_AUTHORIZED_KEYS` | SSH **public** key(s), one per line | in practice yes: without it **nobody can log in** (user `cohost` has no password, root is locked) |

Settings > Secrets and variables > Actions. Repository level (not an environment), because PR plans need the token.
A secret named `NUC_LAB_SSH_AUTHORIZED_KEYS` is **ignored**: the workflow reads `vars.`, not `secrets.` (this happened once;
the run log then shows `TF_VAR_ssh_authorized_keys:` empty). Changing the keys replaces VM 210 on the next apply.
Do **not** set `DEPLOY_ENABLED` for this; it only gates `deploy.yml`.

## One-time preparation (owner, before merging the PR)
1. **NAS**: on the NFS export of `/volume1/CoHostBackup`, add `192.168.1.200` (the control VM) with Read/Write,
   same squash setting as the Proxmox entry.
2. **Proxmox**: Datacenter > Storage > `nas` > Content: tick **Snippets** (keep what is already ticked).
3. **Control VM** (Proxmox > VM 200 > Console, as root): run `infra/nuc/control-nas-mount.sh`
   (clone the repo or paste the script). It mounts the share at `/mnt/cohost-nas` (NFS v3, in `/etc/fstab`),
   creates `terraform/nuc-lab/` and `snippets/`, and tests a write through Docker.
4. **Token privileges**: the `TerraformProv` role from `infra/proxmox/host-setup.sh terraform` is enough
   (clone, disk, cloud-init, network, power, datastore). A token made another way needs the same.
5. Keep `192.168.1.200-220` out of the router's DHCP pool.
6. Create the secret(s) above, then re-run the PR's `NUC Terraform` workflow: the plan must show
   `2 to add` (the snippet and VM 210) and nothing to change or destroy.

Merging then creates the VM. First boot takes a few minutes (package upgrade, Docker, Tailscale);
`/var/lib/cohost-lab-ready` exists when cloud-init is done (`cloud-init status --wait`).

## Logging in
No laptop needed: the key pair lives on the Proxmox host.
```bash
# once, in Proxmox > myproxmox > Shell; put the .pub line in NUC_LAB_SSH_AUTHORIZED_KEYS, then run apply
ssh-keygen -t ed25519 -f ~/.ssh/cohost-lab -N "" -C cohost-lab && cat ~/.ssh/cohost-lab.pub
ssh -i ~/.ssh/cohost-lab cohost@192.168.1.210     # cohost has passwordless sudo and is in the docker group
```
Health check on the VM: `cloud-init status --wait` (`status: done`), `docker run --rm hello-world`, `sudo tailscale status`.

## Tailscale
The node name is `cohost-lab`. A rebuild (destroy + create, or any cloud-init change) leaves the old node registered,
offline, so the new VM joins as `cohost-lab-1`. After a rebuild: Tailscale admin console > Machines, remove the offline
`cohost-lab`, rename `cohost-lab-1` to `cohost-lab`. An ephemeral key would remove old nodes by itself, but the VM would
then drop off the tailnet after any NUC power-off and only come back on the next apply (cloud-init deletes the key after use).

## Rebuild drill
Actions > NUC Terraform > Run workflow (branch `master`): `destroy`, then `apply`. Only VM 210 and its
snippet are touched. Editing `cloud-init/lab.yaml.tftpl` also replaces the VM on the next apply
(the snippet name contains its hash; cloud-init only runs on first boot).

## Notes and limits
- TLS to the Proxmox API is not verified (self-signed, LAN only). To verify: commit the public
  `/etc/pve/pve-root-ca.pem` and pass `SSL_CERT_FILE` in `tf.sh`.
- The state and the snippet contain the Tailscale auth key if one is set. Both live on the NAS, not in Git.
- The control VM can write to the whole `CoHostBackup` share (NFS v3 permissions are per export).
  Jobs on the runner are root-equivalent on that VM, so keep NAS snapshots on for this share.
- `.terraform.lock.hcl` pins bpg/proxmox 0.123.1 and hashicorp/local 2.9.1 (linux_amd64 hashes). Upgrade: `terraform init -upgrade` in the validate job, commit the printed file.
