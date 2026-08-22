# django-saas-starter

Django starter for shipping SaaS products fast.

## Tech stack

- **Django 5.2 on Python 3.13** — class-based views, type hints via django-stubs
- **PostgreSQL 17** — the only supported database, no SQLite fallback
- **django-allauth** — email-only accounts (no usernames) with Google OAuth
- **htmx + Alpine.js** — htmx for anything that reads or writes the database, Alpine for purely client-side state
- **uv** — Python dependency management
- **Docker + just** — containerized dev environment driven by just recipes, with hot reload
- **Gunicorn + WhiteNoise** — production server and static file serving
- **Polar** for billing: org-level subscriptions, hosted checkout + customer portal, webhooks.

## Project layout

- Domain apps live in `apps/` — create new apps there and register them as `apps.<name>`
- Auth is split in two: `accounts` owns the user model, `authn` holds the django-allauth wiring
- Shared, app-agnostic code (middleware, mixins, template tags) lives in `apps/core`
- Settings are split per environment in `config/settings/`: `base.py`, `development.py`, `production.py`
- Project-wide templates in `templates/`, static assets in `static/`

## Prerequisites

- **Docker** — runs the app and database containers; no local Python install needed
- **[just](https://github.com/casey/just)** — command runner for the dev workflow; run `just` to list all recipes
- **uv** - in case you need to install tooling for local development

## Quickstart

```bash
cp .env.example .env  # then set the necessary secrets
just build
just up

# Optionally, create a superuser
just manage createsuperuser
```

All configuration is via environment variables in `.env` — see `.env.example` for the full list. Migrations run automatically on container start. The app is at http://localhost:8000 (admin at `/admin/`), and Postgres data persists in `.data/db/`.

## Common commands

| Command             | Description                     |
| ------------------- | ------------------------------- |
| `just build`        | Build the dev image             |
| `just up`           | Start containers                |
| `just down`         | Stop containers                 |
| `just restart`      | Restart a service (defaults to server) |
| `just logs`         | Tail container logs             |
| `just shell`        | Bash into the Django container  |
| `just manage <cmd>` | Run a Django management command |
| `just test`         | Run the test suite (needs `just up` first) |
| `just lint`         | Pre-commit on staged files      |
| `just lint-all`     | Pre-commit on all files         |

## Polar webhooks

If you wish to receive Polar webhooks on your local machine, [install the Polar CLI](https://polar.sh/docs/integrate/webhooks/locally), log in to your account, and forward events to the webhook endpoint:

```bash
polar login
polar listen http://localhost:8000/app/billing/webhook/
```

Copy the `Secret` printed after connecting into `.env` as `POLAR_WEBHOOK_SECRET`. The webhook view requires it to verify deliveries — without the correct secret you'll get 403s.

## Linting & formatting

Ruff (Python) and djlint (templates) run via pre-commit — config lives in `pyproject.toml`. Run `pre-commit install` once to have the hooks fire automatically on every commit.
