#!/usr/bin/env bash
# Post-install setup of the Proxmox VE host on the Intel NUC. Run as root ON the Proxmox host.
# Idempotent: safe to re-run. See docs/PROXMOX.md.
#
#   bash host-setup.sh repos      # no-subscription repos + full upgrade
#   NAS_IP=192.168.1.20 NAS_EXPORT=/volume1/proxmox bash host-setup.sh nfs
#   bash host-setup.sh template   # Ubuntu 24.04 cloud-init VM template (id 9000)
#   bash host-setup.sh terraform  # API user + token for Terraform (token is printed ONCE)
#   bash host-setup.sh all        # repos + template (+ nfs if NAS_IP is set)
set -euo pipefail

STORAGE="${STORAGE:-local-lvm}"      # where VM disks live (use local-zfs on a ZFS install)
BRIDGE="${BRIDGE:-vmbr0}"
TEMPLATE_ID="${TEMPLATE_ID:-9000}"
NAS_STORAGE_ID="${NAS_STORAGE_ID:-nas}"
IMAGE_URL="${IMAGE_URL:-https://cloud-images.ubuntu.com/noble/current}"
IMAGE_FILE="noble-server-cloudimg-amd64.img"

die() { echo "ERROR: $*" >&2; exit 1; }
log() { printf '\033[1;36m==>\033[0m %s\n' "$*"; }

require_pve() {
  [ "$(id -u)" -eq 0 ] || die "run as root"
  command -v pveversion >/dev/null || die "this must run on the Proxmox VE host"
}

cmd_repos() {
  # shellcheck disable=SC1091
  . /etc/os-release
  local codename="${VERSION_CODENAME:?}"
  log "Proxmox $(pveversion | cut -d/ -f2) on Debian ${codename}: switching to the no-subscription repository"
  local d=/etc/apt/sources.list.d
  mkdir -p /root/apt-disabled
  # Enterprise repos need a paid subscription and make 'apt update' fail; park them, never delete.
  for f in "$d"/pve-enterprise.* "$d"/ceph.*; do
    [ -e "$f" ] && mv -f "$f" /root/apt-disabled/ || true
  done
  if [ "$codename" = "bookworm" ]; then
    echo "deb http://download.proxmox.com/debian/pve ${codename} pve-no-subscription" > "$d/pve-no-subscription.list"
  else
    cat > "$d/pve-no-subscription.sources" <<EOF
Types: deb
URIs: http://download.proxmox.com/debian/pve
Suites: ${codename}
Components: pve-no-subscription
Signed-By: /usr/share/keyrings/proxmox-archive-keyring.gpg
EOF
  fi
  apt-get update -y
  DEBIAN_FRONTEND=noninteractive apt-get dist-upgrade -y
  apt-get install -y libguestfs-tools unattended-upgrades >/dev/null
  log "repos done. Reboot if the kernel was upgraded."
}

cmd_nfs() {
  : "${NAS_IP:?set NAS_IP}" "${NAS_EXPORT:?set NAS_EXPORT, e.g. /volume1/proxmox}"
  if pvesm status 2>/dev/null | awk '{print $1}' | grep -qx "$NAS_STORAGE_ID"; then
    log "storage '$NAS_STORAGE_ID' already exists"
  else
    log "adding NFS storage '$NAS_STORAGE_ID' (${NAS_IP}:${NAS_EXPORT})"
    # backup = vzdump + pg_dump copies; iso/vztmpl = installers and CT templates; snippets = cloud-init files.
    pvesm add nfs "$NAS_STORAGE_ID" --server "$NAS_IP" --export "$NAS_EXPORT" \
      --content backup,iso,vztmpl,snippets --options vers=4.1
  fi
  pvesm status | grep -E "^(Name|${NAS_STORAGE_ID}) "
}

cmd_template() {
  if qm status "$TEMPLATE_ID" >/dev/null 2>&1; then
    log "VM ${TEMPLATE_ID} already exists, nothing to do"; return
  fi
  local work; work="$(mktemp -d)"; trap 'rm -rf "$work"' EXIT
  log "downloading the Ubuntu 24.04 cloud image and verifying its checksum"
  curl -fsSL -o "$work/$IMAGE_FILE" "$IMAGE_URL/$IMAGE_FILE"
  curl -fsSL -o "$work/SHA256SUMS" "$IMAGE_URL/SHA256SUMS"
  (cd "$work" && grep " \*${IMAGE_FILE}\$" SHA256SUMS | sha256sum -c -)
  log "baking qemu-guest-agent into the image (Terraform needs it to read the VM's IP)"
  virt-customize -a "$work/$IMAGE_FILE" --install qemu-guest-agent --run-command 'systemctl enable qemu-guest-agent' >/dev/null
  log "creating template ${TEMPLATE_ID}"
  qm create "$TEMPLATE_ID" --name ubuntu-2404-cloud --memory 2048 --cores 2 \
    --net0 "virtio,bridge=${BRIDGE}" --scsihw virtio-scsi-pci --ostype l26 \
    --serial0 socket --vga serial0 --agent enabled=1
  qm set "$TEMPLATE_ID" --scsi0 "${STORAGE}:0,import-from=$work/$IMAGE_FILE" >/dev/null
  qm set "$TEMPLATE_ID" --ide2 "${STORAGE}:cloudinit" --boot order=scsi0 >/dev/null
  qm template "$TEMPLATE_ID"
  log "template ready: id ${TEMPLATE_ID}"
}

cmd_terraform() {
  local user="terraform@pve" role="TerraformProv"
  local privs="Datastore.Allocate Datastore.AllocateSpace Datastore.AllocateTemplate Datastore.Audit Pool.Allocate Sys.Audit Sys.Console Sys.Modify SDN.Use VM.Allocate VM.Audit VM.Clone VM.Config.CDROM VM.Config.Cloudinit VM.Config.CPU VM.Config.Disk VM.Config.HWType VM.Config.Memory VM.Config.Network VM.Config.Options VM.Migrate VM.PowerMgmt User.Modify"
  if ! pveum role list | grep -qw "$role"; then
    log "creating role ${role}"
    pveum role add "$role" -privs "$privs"
  fi
  if ! pveum user list | grep -qF "$user"; then
    log "creating user ${user}"
    pveum user add "$user" --comment "Terraform (infra/nuc/terraform)"
  fi
  pveum aclmod / -user "$user" -role "$role"
  if pveum user token list "$user" | grep -qw provider; then
    log "token ${user}!provider already exists. To rotate: pveum user token remove ${user} provider, then re-run."
  else
    log "creating API token. The secret is shown ONCE: store it in your password manager now."
    pveum user token add "$user" provider --privsep 0
  fi
}

main() {
  require_pve
  case "${1:-}" in
    repos) cmd_repos ;;
    nfs) cmd_nfs ;;
    template) cmd_template ;;
    terraform) cmd_terraform ;;
    all) cmd_repos; [ -n "${NAS_IP:-}" ] && cmd_nfs; cmd_template ;;
    *) die "usage: $0 {repos|nfs|template|terraform|all}" ;;
  esac
}
main "$@"
