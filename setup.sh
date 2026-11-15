#!/usr/bin/env bash
# CoHost setup. Idempotent: never overwrites an existing .env or secret file.
#
#   ./setup.sh dev                       local venv + SQLite, ready for runserver
#   ./setup.sh secrets DOMAIN EMAIL      generate ./secrets/* and .env.prod
#   ./setup.sh prod    DOMAIN EMAIL      secrets + docker compose up (HTTPS via Caddy)
#   ./setup.sh check                     preflight (tooling, secret hygiene)
set -euo pipefail
cd "$(dirname "$0")"

say()  { printf '\033[1;36m==>\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33mwarn:\033[0m %s\n' "$*" >&2; }
die()  { printf '\033[1;31merror:\033[0m %s\n' "$*" >&2; exit 1; }
rand() { python3 -c "import secrets,sys; print(secrets.token_$1($2))"; }   # hex|urlsafe N

need_python() {
  command -v python3 >/dev/null || die "python3 not found"
  python3 -c 'import sys; sys.exit(sys.version_info < (3, 12))' || die "Python 3.12+ required (found $(python3 -V))"
}

write_secret() {  # write_secret <file> <value> — create only if missing, mode 600
  local f="secrets/$1"
  if [[ -e $f ]]; then echo "   keep  $f"; else umask 077; printf '%s' "$2" > "$f"; echo "   new   $f"; fi
}

cmd_dev() {
  need_python
  say "Creating virtualenv (.venv) and installing requirements-dev.txt"
  python3 -m venv .venv
  .venv/bin/pip install --quiet --upgrade pip
  .venv/bin/pip install --quiet -r requirements-dev.txt

  if [[ ! -e .env ]]; then
    say "Writing .env (generated SECRET_KEY, DEBUG=True, SQLite)"
    umask 077
    sed -e "s|^SECRET_KEY=.*|SECRET_KEY=$(rand urlsafe 50)|" \
        -e 's|^DEBUG=.*|DEBUG=True|' \
        -e 's|^ALLOWED_HOSTS=.*|ALLOWED_HOSTS=localhost,127.0.0.1|' \
        -e '/^DATABASE_URL=/s|^|# |' -e '/^CACHE_URL=/s|^|# |' \
        -e 's|^EMAIL_BACKEND=.*|EMAIL_BACKEND=django.core.mail.backends.console.EmailBackend|' \
        -e 's|^SECURE_SSL_REDIRECT=.*|SECURE_SSL_REDIRECT=False|' \
        -e 's|^SECURE_HSTS_SECONDS=.*|SECURE_HSTS_SECONDS=0|' \
        -e 's|^SESSION_COOKIE_SECURE=.*|SESSION_COOKIE_SECURE=False|' \
        -e 's|^CSRF_COOKIE_SECURE=.*|CSRF_COOKIE_SECURE=False|' \
        -e '/^SENTRY_DSN=/s|^|# |' .env.example > .env
  else
    echo "   keep  .env"
  fi
  mkdir -p logs media
  .venv/bin/python manage.py migrate --noinput
  .venv/bin/python manage.py createcachetable
  command -v chromium chromium-browser google-chrome >/dev/null 2>&1 \
    || warn "No Chromium/Chrome found: the Airbnb scraper needs one (manual listings work without)."
  say "Done. Next:  source .venv/bin/activate && python manage.py createsuperuser && python manage.py runserver"
}

cmd_secrets() {
  local domain=${1:-} email=${2:-}
  [[ -n $domain && -n $email ]] || die "usage: ./setup.sh secrets <domain> <acme-email>"
  need_python
  say "Generating secrets in ./secrets (mode 700, files 600, git-ignored)"
  umask 077; mkdir -p secrets; chmod 700 secrets
  local pg redis
  pg=$(rand hex 24); redis=$(rand hex 24)
  write_secret secret_key        "$(rand urlsafe 64)"
  write_secret postgres_password "$pg"
  write_secret redis_password    "$redis"
  # hex passwords need no URL-escaping
  write_secret database_url      "postgresql://cohost:${pg}@db:5432/cohost"
  write_secret cache_url         "redis://:${redis}@redis:6379/1"
  write_secret email_host_password ""
  write_secret sentry_dsn          ""
  if [[ ! -e .env.prod ]]; then
    cat > .env.prod <<EOF
# Non-secret production config (secrets live in ./secrets/*)
DOMAIN=${domain}
ACME_EMAIL=${email}
EMAIL_HOST=smtp.example.com
EMAIL_HOST_USER=
DEFAULT_FROM_EMAIL=noreply@${domain}
# Start with a short HSTS window; raise to 31536000 once HTTPS is confirmed working.
SECURE_HSTS_SECONDS=300
EOF
    echo "   new   .env.prod"
  else echo "   keep  .env.prod"; fi
  say "Still to fill in: secrets/email_host_password, secrets/sentry_dsn, EMAIL_HOST* in .env.prod"
  say "Back secrets/ up in a password manager, or encrypt for git with SOPS+age (docs/ARCHITECTURE.md §5)."
}

cmd_prod() {
  command -v docker >/dev/null || die "docker not found (https://docs.docker.com/engine/install/)"
  docker compose version >/dev/null 2>&1 || die "docker compose plugin not found"
  cmd_secrets "$@"
  say "Building and starting the stack"
  docker compose -f docker-compose.prod.yml --env-file .env.prod up -d --build
  say "Create the first admin:  docker compose -f docker-compose.prod.yml --env-file .env.prod exec web python manage.py createsuperuser"
}

cmd_check() {
  local bad=0
  tracked=$(git ls-files | grep -E '(^|/)(\.env(\..*)?|secrets/.*|cookies\.txt|db\.sqlite3|.*\.pem|.*\.key)$' | grep -v '\.example$' || true)
  [[ -z $tracked ]] || { warn "sensitive files tracked in git:"; echo "$tracked"; bad=1; }
  for f in .env .env.prod; do
    [[ -e $f ]] && [[ $(stat -c %a "$f") != 600 ]] && { warn "$f should be chmod 600"; bad=1; }
  done
  [[ -d secrets && $(stat -c %a secrets) != 700 ]] && { warn "secrets/ should be chmod 700"; bad=1; }
  command -v docker >/dev/null || warn "docker not installed (only needed for prod)"
  [[ $bad == 0 ]] && say "preflight OK" || exit 1
}

case "${1:-}" in
  dev)     shift; cmd_dev "$@" ;;
  secrets) shift; cmd_secrets "$@" ;;
  prod)    shift; cmd_prod "$@" ;;
  check)   shift; cmd_check "$@" ;;
  *) sed -n '2,8p' "$0" | sed 's/^# \{0,1\}//'; exit 1 ;;
esac
