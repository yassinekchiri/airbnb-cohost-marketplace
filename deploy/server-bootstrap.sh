#!/usr/bin/env bash
# Run once, as root, on a fresh Ubuntu 24.04 cloud VM (also usable as cloud-init user-data).
#   DEPLOY_PUBKEY="ssh-ed25519 AAAA... gh-actions-deploy" TS_AUTHKEY=tskey-auth-... bash server-bootstrap.sh
# Afterwards the first `Deploy` workflow run installs the app, generates secrets and starts it.
set -euo pipefail
: "${DEPLOY_PUBKEY:?public half of the DEPLOY_SSH_KEY secret}"

export DEBIAN_FRONTEND=noninteractive
apt-get update -y && apt-get install -y ca-certificates curl ufw unattended-upgrades fail2ban python3 age
command -v docker >/dev/null || curl -fsSL https://get.docker.com | sh
systemctl enable --now docker
command -v tailscale >/dev/null || curl -fsSL https://tailscale.com/install.sh | sh

id deploy >/dev/null 2>&1 || useradd --create-home --shell /bin/bash --groups docker deploy
install -d -m 700 -o deploy -g deploy /home/deploy/.ssh
grep -qxF "$DEPLOY_PUBKEY" /home/deploy/.ssh/authorized_keys 2>/dev/null || echo "$DEPLOY_PUBKEY" >> /home/deploy/.ssh/authorized_keys
chown deploy:deploy /home/deploy/.ssh/authorized_keys; chmod 600 /home/deploy/.ssh/authorized_keys
install -d -m 750 -o deploy -g deploy /opt/cohost

# Join the tailnet; SSH is reachable ONLY over it.
[[ -n ${TS_AUTHKEY:-} ]] && tailscale up --authkey "$TS_AUTHKEY" --hostname cohost-prod --ssh=false

cat > /etc/ssh/sshd_config.d/10-cohost.conf <<'EOF'
PasswordAuthentication no
KbdInteractiveAuthentication no
PermitRootLogin no
AllowUsers deploy
EOF
systemctl reload ssh

ufw default deny incoming && ufw default allow outgoing
ufw allow 80/tcp && ufw allow 443/tcp && ufw allow 443/udp
ufw allow in on tailscale0 to any port 22 proto tcp     # SSH only via the tailnet
ufw --force enable

echo '0 4 * * 0 root docker image prune -af --filter "until=720h" >/dev/null 2>&1' > /etc/cron.d/docker-prune
echo "Host key to store in the GitHub variable DEPLOY_HOST_KEY:"; cut -d' ' -f1,2 /etc/ssh/ssh_host_ed25519_key.pub
