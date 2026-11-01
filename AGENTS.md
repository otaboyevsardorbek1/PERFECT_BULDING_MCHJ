# AGENTS.md

This is effectively a single application. All runtime code lives in
`construction_factory_bot/`; the repository root only contains docs, workflows,
a local `venv/`, and a standalone analyzer. Run every app/test command from
`construction_factory_bot/`: `config.py` resolves SQLite as
`database/construction.db` **relative to the current directory**, so running
from the root silently creates/uses the wrong database. Running `pytest` from
the root also collects the non-test demo `shablon_info/test_pdf.py` and aborts.

## Runtime shape

| Piece | Entrypoint | Notes |
| --- | --- | --- |
| Telegram bot | `main.py` | aiogram 3.22, long polling. Owns the only background loop: notifications, debt SMS, daily digest, scheduled backup. Running only the API means those never fire. |
| REST API | `dashboard/app.py` | FastAPI on `:8000`. Routers are registered in order `api_v5 -> api_v53 -> api_v55 -> api_v6 -> api_v3` so literal paths beat parameterized ones. |
| Web UI | `web/server.js` | Plain Node HTTP server on `:3000`. **Zero dependencies**; serves `web/public` and proxies only `/api/*` + `/health` to `PY_API_URL`. No `npm install` or build step. |
| Database | `database/models.py` | Sync SQLAlchemy. SQLite by default; `USE_POSTGRESQL=true` switches to PostgreSQL. |

`web/public` is a hand-written SPA (`app.js`, `app_v5.js`, `app_v6.js`,
`shop.html`), not a bundled framework app. Edit the files directly.

Docs worth opening: root `construction_factory_bot.md` is the ~10k-line Uzbek
technical specification; `construction_factory_bot/README.md` is the
implementation/API guide; `TAHLIL.md` is the audit report. `PROJECT_GUIDE.md`
documents an Alembic migration setup that was never adopted — trust code and
config over it.

## Commands

```bash
cd construction_factory_bot

# existing local venv is at ../venv (Python 3.13); CI uses Python 3.11
source ../venv/bin/activate
pip install -r requirements.txt
pip install pytest-timeout   # required by pytest.ini but missing from requirements.txt

# API
python -m uvicorn dashboard.app:app --host 0.0.0.0 --port 8000

# Bot
python main.py

# Web (from construction_factory_bot/web)
PORT=3000 PY_API_URL=http://127.0.0.1:8000 node server.js

# Tests
pytest                                              # full suite
pytest tests/test_api/test_auth.py -q               # one file
pytest tests/test_utils/test_backup.py::TestEncrypt::test_encrypt_decrypt_roundtrip

# CI-equivalent static checks
python -m compileall -q . -x '/(\.git|\.pytest_cache|__pycache__|node_modules)/'
node --check web/server.js && node --check web/public/app.js

# Docker (api + web + bot + event-worker)
docker compose up -d --build
docker compose logs -f bot
```

Password bootstrap:
`python -m dashboard.auth set-password --phone +998... --password ...`,
`python -m dashboard.auth list-users` (also `WEB_ADMIN_PASSWORD` on first run).
Session lifetimes are clamped to 5–30 minutes in `config.py`.

## Testing quirks

- `tests/conftest.py` forces `TEST_MODE` and per-test in-memory SQLite.
- `tests/test_api/conftest.py` autouse-overrides `get_current_user` to a
  direktor. API tests therefore **do not verify auth or role permissions**;
  real auth is covered only in `tests/test_api/test_auth.py`. Add an explicit
  auth test when changing permissions.
- pytest runs in `asyncio_mode=auto`.
- Historically (clean `HEAD` `15ae965`, 2026-10) the suite had 7 failures:
  4 timezone/document-numbering bugs (`test_api_v5.py::test_payments_list_create_daily`,
  `::test_reports_periods`, `test_cash_shift.py::test_can_open_after_close`,
  `test_shop_orders.py::test_cancel_pending_order`) and 3 backup-encryption
  tests when `cryptography` was missing. These are fixed in the current tree
  (UTC numbering/filters, placeholder-aware config, `cryptography` installed):
  the full suite is **700 passed**. Re-confirm against a clean worktree before
  attributing new failures to your change.
- `STRICT_STOCK_CHECK` (default `true`) blocks overselling only for products
  with an inbound stock ledger (`PRODUCTION`/`INVENTORY`/`RETURN`). Legacy
  untracked products stay sellable; set it to `false` only for migrations.
- This checkout may contain uncommitted `fix_all*`/`repair_all.py` repair work.
  If the suite is much redder than the baseline above, inspect `git diff` before
  editing. Never run `fix_all.py`, `fix_all_v2.py`, or `repair_all.py` unless the
  user asks — they rewrite source files and create `.fix_backup_*` copies.

## Schema and API rules

- There are **no Alembic migrations** despite the dependency and docs.
  `models.upgrade_schema()` runs on API import and bot startup. When adding a
  column, also add it to `EXTRA_COLUMNS` in `database/models.py` or existing
  SQLite databases will not get it. The Postgres path only runs `create_all`, so
  existing PG tables need manual DDL.
- Put endpoints in the correct version module. New literal routes can be
  shadowed by older parameterized routes (e.g. `/api/customers/{id}`); check
  registration order in `dashboard/app.py`.
- Auth is `dashboard/auth.py`: use `Depends(require_role("<module>", edit=...))`.
  Module names and permissions come from `config.ROLES`; add a new module to
  every relevant role's `can_view`/`can_edit` lists. The
  `CostVisibilityMiddleware` strips cost fields server-side for `see_cost=false`
  roles — do not “restore” them.
- Intentionally public (do not add Bearer auth): `/api/login`,
  `/api/password-reset/request|complete`, `/api/shop/*`,
  `/api/payments/click|payme` (verified by gateway signatures), `/health`.
- Bot handlers: every `handlers/*.py` exposes `register_handlers_x(dp)`. Import
  and call it in `main.py`; also add commands to `set_my_commands` if they belong
  in the Telegram menu. The global session middleware blocks everything not in
  `_SESSION_FREE_COMMANDS` (`utils/access.py`) — add new pre-login commands there.

## Repository gotchas

- `run.sh`, `stop.sh`, and `status.sh` are stale: they assume Flask/gunicorn on
  port 5000. The real service is FastAPI on 8000. Do not use them.
- `infra/deploy.sh` expects `infra/terraform/`, which is absent; the K8s/Helm/
  Istio manifests are not exercised by CI. Do not treat `infra/` as a working
  deploy path without checking.
- `database/construction.db` is tracked in git. Avoid committing local runtime
  data changes; `.env` and `.web_secret` are ignored and must never be printed
  or committed.
- `fix_all*.py`, `repair_all.py`, `.fix_backup_*`, and `*.broken_*.bak` are
  one-off repair artifacts, not application code.
- `.mcp.json` configures a read-only Supabase MCP server; it is unrelated to the
  app database (SQLite/PostgreSQL).
- User-facing strings, comments, and documentation are written in Uzbek. Keep
  that convention. There is no lint/format/typecheck gate; CI only runs
  `compileall`, pytest, `node --check`, and a Docker build — do not reformat
  unrelated files.
