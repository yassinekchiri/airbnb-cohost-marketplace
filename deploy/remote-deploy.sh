#!/usr/bin/env bash
# Runs ON the production VM, as the `deploy` user, fed over SSH by .github/workflows/deploy.yml.
#
#   bash -s -- ghcr.io/<owner>/<repo>@sha256:<digest>   deploy this exact image
#   bash -s -- --rollback                               go back to the previous image
#   bash -s -- --status
#
# Contract: migrations are additive (expand/contract), so the previous image keeps
# working against the new schema. That is what makes "just swap the image back" a valid rollback.
set -euo pipefail

APP=${APP_DIR:-/opt/cohost}
cd "$APP"
mkdir -p .release incoming
exec 9>.release/lock
flock -n 9 || { echo "another deploy is running"; exit 1; }

say() { printf '\n==> %s\n' "$*"; }
compose() { docker compose -f docker-compose.prod.yml --env-file .env.prod --env-file .release/web.env "$@"; }
current() { grep -s '^WEB_IMAGE=' .release/web.env | cut -d= -f2- || true; }
set_image() { printf 'WEB_IMAGE=%s\n' "$1" > .release/web.env.tmp && mv .release/web.env.tmp .release/web.env; }
touch .release/web.env

swap_web() {  # swap_web <image>: run that image as `web` and wait until Docker reports it healthy
  set_image "$1"
  compose up -d --no-deps --wait --wait-timeout 150 web
}

case "${1:-}" in
  --status)
    echo "current : $(current)"; echo "previous: $(cat .release/previous 2>/dev/null || echo -)"
    compose ps; exit 0 ;;
  --rollback)
    prev=$(cat .release/previous 2>/dev/null || true)
    [[ -n $prev ]] || { echo "no previous release recorded"; exit 1; }
    cur=$(current)
    say "Rolling back to $prev"
    swap_web "$prev"
    echo "$cur" > .release/previous
    exit 0 ;;
esac

NEW=${1:?usage: remote-deploy.sh <image@sha256:digest> | --rollback | --status}
[[ $NEW =~ ^ghcr\.io/[a-z0-9._/-]+@sha256:[0-9a-f]{64}$ ]] || { echo "refusing: not a pinned GHCR digest: $NEW"; exit 1; }

say "Installing config shipped with this release"
for f in docker-compose.prod.yml Caddyfile setup.sh; do
  [[ -f incoming/$f ]] && cat "incoming/$f" > "$f"   # `cat >` keeps the inode, so the Caddyfile bind mount stays valid
done
chmod +x setup.sh

if [[ ! -f secrets/secret_key ]]; then
  say "First deploy: generating secrets for ${DOMAIN:?DOMAIN required on first deploy}"
  ./setup.sh secrets "$DOMAIN" "${ACME_EMAIL:?ACME_EMAIL required on first deploy}"
fi
# Third-party secrets are pushed from GitHub Environment secrets (never via argv).
[[ -n ${EMAIL_HOST_PASSWORD:-} ]] && { umask 077; printf '%s' "$EMAIL_HOST_PASSWORD" > secrets/email_host_password; }
[[ -n ${SENTRY_DSN:-} ]]          && { umask 077; printf '%s' "$SENTRY_DSN" > secrets/sentry_dsn; }

PREV=$(current)
say "Pulling $NEW"
docker pull "$NEW"

say "Starting data services"
set_image "$NEW"
compose up -d --wait db redis

say "Running migrations"
if ! compose run --rm migrate; then
  echo "migration failed; keeping ${PREV:-<none>}"; [[ -n $PREV ]] && set_image "$PREV"; exit 1
fi

say "Swapping web to the new image"
if ! swap_web "$NEW"; then
  echo "new web never became healthy; rolling back"
  compose logs --tail=80 web || true
  [[ -n $PREV ]] && swap_web "$PREV"
  exit 1
fi

say "Applying proxy/backup config"
compose up -d caddy backup
compose exec -T caddy caddy reload --config /etc/caddy/Caddyfile 2>/dev/null || true

[[ -n $PREV && $PREV != "$NEW" ]] && echo "$PREV" > .release/previous
echo "$(date -u +%FT%TZ) $NEW" >> .release/history
say "Deployed $NEW"
