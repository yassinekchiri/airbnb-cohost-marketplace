#!/usr/bin/env bash
# Run Terraform for infra/nuc/terraform in the official image, on the runner's Docker host.
#
#   tf.sh validate          fmt check + validate, no state, no credentials (GitHub-hosted runner)
#   tf.sh plan|apply|destroy  on the NUC runner (label nuc), state + snippets on the NAS
#
# Why a container: the NUC runner may itself be a container (infra/nuc/runner-compose.yml) that cannot
# see the control VM's NFS mount, but it drives the VM's Docker daemon. Bind mounts are resolved on
# the VM, and the runner work dir has the same path on both sides, so this works for a containerised
# or a native runner alike.
#
# Inputs (environment): PROXMOX_VE_API_TOKEN (required for plan/apply/destroy),
#   TF_VAR_ssh_authorized_keys, TF_VAR_tailscale_auth_key (optional).
#   Values are passed with `-e NAME`, never on a command line.
set -euo pipefail

TF_IMAGE="${TF_IMAGE:-hashicorp/terraform:1.17.2}"
NAS_MOUNT="${NAS_MOUNT:-/mnt/cohost-nas}"   # control VM: 192.168.1.15:/volume1/CoHostBackup (infra/nuc/control-nas-mount.sh)
STATE_DIR="$NAS_MOUNT/terraform/nuc-lab"
SNIPPETS_DIR="$NAS_MOUNT/snippets"           # = Proxmox storage "nas", content "snippets"
here="$(cd "$(dirname "$0")" && pwd)"

action="${1:-}"
init='terraform init -input=false -no-color -backend-config=path=/nas/terraform/nuc-lab/terraform.tfstate'
case "$action" in
  validate) inner='terraform fmt -check -recursive -diff && terraform init -input=false -no-color -backend=false && terraform validate -no-color' ;;
  plan)     inner="$init && terraform plan -input=false -no-color -lock-timeout=10m" ;;
  apply)    inner="$init && terraform apply -input=false -no-color -lock-timeout=10m -auto-approve && terraform output -no-color" ;;
  destroy)  inner="$init && terraform destroy -input=false -no-color -lock-timeout=10m -auto-approve" ;;
  *) echo "usage: $0 {validate|plan|apply|destroy}" >&2; exit 2 ;;
esac

args=(--rm --user "$(id -u):$(id -g)" -e HOME=/tmp -e TF_DATA_DIR=/tmp/tf-data -e TF_IN_AUTOMATION=1 -e TF_INPUT=0
      --mount "type=bind,src=$here,dst=/work" -w /work)

if [ "$action" != validate ]; then
  [ -n "${PROXMOX_VE_API_TOKEN:-}" ] || { echo "ERROR: PROXMOX_VE_API_TOKEN is empty: create the repository secret (infra/nuc/terraform/README.md)" >&2; exit 1; }
  # type=bind fails if the directory is missing, so state can never silently land on the VM's local disk.
  args+=(--mount "type=bind,src=$STATE_DIR,dst=/nas/terraform/nuc-lab"
         --mount "type=bind,src=$SNIPPETS_DIR,dst=/nas/snippets"
         -e PROXMOX_VE_API_TOKEN -e TF_VAR_ssh_authorized_keys -e TF_VAR_tailscale_auth_key)
  # The marker is created ON the NAS by control-nas-mount.sh: its presence proves the NFS share is mounted.
  inner="test -f /nas/terraform/nuc-lab/.cohost-nas-marker || { echo 'ERROR: NAS not mounted on the control VM (run infra/nuc/control-nas-mount.sh)'; exit 1; }; $inner"
fi

exec docker run "${args[@]}" --entrypoint /bin/sh "$TF_IMAGE" -ec "$inner"
