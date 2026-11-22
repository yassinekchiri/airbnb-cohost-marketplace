#!/usr/bin/env bash
# Run once, as root, on the hand-made "control" VM (id 200, 192.168.1.200) that hosts the NUC runner.
# Mounts the NAS share that Proxmox also uses as storage "nas", for the lab's Terraform state and
# cloud-init snippets. Idempotent.
#
#   bash infra/nuc/control-nas-mount.sh
#
# Before: on the NAS, allow 192.168.1.200 (read/write) on the NFS export of /volume1/CoHostBackup,
# and on Proxmox enable content "Snippets" on storage "nas" (Datacenter > Storage > nas > Content).
set -euo pipefail
NAS="${NAS:-192.168.1.15:/volume1/CoHostBackup}"
MNT="${MNT:-/mnt/cohost-nas}"
OPTS="${OPTS:-vers=3,hard,noatime,_netdev,nofail}"   # v3 like the Proxmox storage; nfs-common gives NLM locking

[ "$(id -u)" -eq 0 ] || { echo "run as root" >&2; exit 1; }
command -v mount.nfs >/dev/null || { apt-get update -y && apt-get install -y nfs-common; }
install -d -m 755 "$MNT"
if ! grep -qE "^[^#]*[[:space:]]${MNT}[[:space:]]" /etc/fstab; then
  printf '%s %s nfs %s 0 0\n' "$NAS" "$MNT" "$OPTS" >> /etc/fstab
  systemctl daemon-reload
fi
mountpoint -q "$MNT" || mount "$MNT"
mountpoint -q "$MNT" || { echo "mount of $MNT failed" >&2; exit 1; }

install -d -m 755 "$MNT/snippets"
install -d -m 700 "$MNT/terraform" "$MNT/terraform/nuc-lab"
touch "$MNT/terraform/nuc-lab/.cohost-nas-marker"
# Write test from the same Docker daemon the runner uses (catches NAS squash/permission problems).
docker run --rm --mount "type=bind,src=$MNT/terraform/nuc-lab,dst=/s" alpine:3.20 \
  sh -c 'echo ok > /s/.write-test && rm /s/.write-test' && echo "NAS ready at $MNT (state: $MNT/terraform/nuc-lab)"
