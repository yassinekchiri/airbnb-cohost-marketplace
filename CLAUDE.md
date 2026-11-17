# CoHost: working agreement for Claude sessions

Django 5.2 marketplace where Airbnb hosts find co-hosts. App `hello`, project `helloworld`.
Users: Morocco first, global later. Repo is private; development happens in Claude Code on the web (no laptop).

## Run / test
- `./setup.sh dev` then `source .venv/bin/activate` (SQLite, console email).
- `pytest` (tests/ is hermetic: locmem cache, in-memory storage). `ruff check .`
- `python manage.py makemigrations --check --dry-run` must be clean.
- `python deploy/smoke.py http://127.0.0.1:8000` black-box check against a running server.

## Rules
- Work on a branch `claude/<topic>`, open a PR to `master`; never push to `master`. CI check `CI / ci-ok` must pass.
- Migrations must be **additive** (rollback swaps the image without reverting the DB).
- Never commit secrets. Secrets are files (`NAME_FILE`) in production; see `docs/ARCHITECTURE.md` section 5.
- Scraper URLs go through `_validate_scraper_url` (hostname match, not substring). Keep tests/test_security.py green.
- User-facing name is "CoHost" (no trailing "r").

## Map
- `docs/ARCHITECTURE.md` stack and secrets; `docs/CICD.md` pipeline runbook.
- `.github/workflows/` ci, deploy, nightly, lab (the Claude GitHub App has the Workflows permission, so Claude can edit them). `deploy/` smoke test and server scripts. `infra/nuc/` home test lab.
- `docker-compose.prod.yml` + `Caddyfile` production; `docker-compose.ci.yml` throwaway test stack.

## Open work
Celery async scraping + isolated scraper image (Phase 6); media to object storage (django-storages);
Terraform for the cloud VM/buckets/DNS; Arabic/French i18n + RTL; Playwright E2E.
