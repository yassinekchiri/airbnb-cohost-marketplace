#!/usr/bin/env bash
# Run once, as root, inside a fresh Ubuntu 24.04 VM on the NUC (ESXi).
#   GITHUB_REPO=owner/repo RUNNER_PAT=github_pat_xxx bash bootstrap-runner-vm.sh
set -euo pipefail
: "${GITHUB_REPO:?}" "${RUNNER_PAT:?}"

apt-get update -y && apt-get install -y ca-certificates curl ufw unattended-upgrades python3
command -v docker >/dev/null || curl -fsSL https://get.docker.com | sh
systemctl enable --now docker

# No inbound at all except SSH from the LAN admin range; everything else is outbound-only.
ufw default deny incoming && ufw default allow outgoing
ufw allow from "${ADMIN_CIDR:-192.168.0.0/16}" to any port 22 proto tcp
ufw --force enable

install -d -m 700 /opt/runner && cd /opt/runner
cp "$(dirname "$0")/runner-compose.yml" docker-compose.yml
umask 077
printf 'GITHUB_REPO=%s\nRUNNER_PAT=%s\n' "$GITHUB_REPO" "$RUNNER_PAT" > .env
docker compose up -d
# Reclaim disk from old test stacks and images every night.
echo '30 4 * * * root docker system prune -af --filter "until=48h" >/dev/null 2>&1' > /etc/cron.d/docker-prune
echo "Runner registered as label 'nuc'. Check: GitHub repo > Settings > Actions > Runners"
