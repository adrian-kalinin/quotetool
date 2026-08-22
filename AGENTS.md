# Agent Guidelines

## Coding Principles

### 1. Think Before Coding

**Don't assume. Don't hide confusion. Surface tradeoffs.**

Before implementing:
- State your assumptions explicitly. If uncertain, ask.
- If multiple interpretations exist, present them - don't pick silently.
- If a simpler approach exists, say so. Push back when warranted.
- If something is unclear, stop. Name what's confusing. Ask.

### 2. Simplicity First

**Minimum code that solves the problem. Nothing speculative.**

- No features beyond what was asked.
- No abstractions for single-use code.
- No "flexibility" or "configurability" that wasn't requested.
- No error handling for impossible scenarios.
- If you write 200 lines and it could be 50, rewrite it.

Ask yourself: "Would a senior engineer say this is overcomplicated?" If yes, simplify.

### 3. Surgical Changes

**Touch only what you must. Clean up only your own mess.**

When editing existing code:
- Don't "improve" adjacent code, comments, or formatting.
- Don't refactor things that aren't broken.
- Match existing style, even if you'd do it differently.
- If you notice unrelated dead code, mention it - don't delete it.

When your changes create orphans:
- Remove imports/variables/functions that YOUR changes made unused.
- Don't remove pre-existing dead code unless asked.

The test: Every changed line should trace directly to the user's request.

## Project Guidelines

### Tech Stack

- **Python 3.13** with **Django 5.2**; class-based views.
- **uv** is the package manager (`uv.lock`, `pyproject.toml`).
- **PostgreSQL 17** as the database (no SQLite fallback).
- **django-allauth** for auth: email-only accounts, no username. Google OAuth via `socialaccount`..
- **Polar** (polar-sdk, `polar.v2026_04`) for billing: org-level subscriptions, hosted checkout + customer portal, webhooks.
- **htmx** for server-driven interactivity: any change that needs a DB read/write goes through HTMX. 
- **Alpine.js** for purely client-side state with no server round-trip.

### Coding Style

- **ruff** with all rules enabled plus the ignores in `pyproject.toml`. Line length 120; isort is `force-single-line` (one import per line).
- **djlint** formats and lints Django HTML templates (profile `django`, indent 2, max line 120).
- **django-stubs** is installed — add type hints to function/method signatures (params and return types). Don't annotate every local variable; let inference handle the rest.

### Development

Local dev runs in Docker via `just` (the `justfile` is the source of truth):

- `just build` — build the dev image (`docker/docker-compose.dev.yml`)
- `just up` / `just down` — start/stop containers
- `just logs` — tail logs
- `just shell` — bash into the Django container
- `just manage <cmd>` — run `python manage.py <cmd>` inside the container
- `just test` — run the Django test suite (unittest-style, in `tests/` packages per app)
- `just lint` — pre-commit on staged files; `just lint-all` — on all files

The dev server runs inside the `server` container; the `database` container is Postgres.
