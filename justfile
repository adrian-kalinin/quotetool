set dotenv-load := true

COMPOSE := "docker compose -f docker/docker-compose.dev.yml"

# Show available commands
_default:
    @just --list --unsorted

# Build Docker image
build *args:
    @echo "{{ MAGENTA }}Building image...{{ NORMAL }}"
    @{{ COMPOSE }} build {{ args }}

# Start application in detached mode
up:
    @echo "{{ MAGENTA }}Starting containers...{{ NORMAL }}"
    @{{ COMPOSE }} up -d --remove-orphans

# Shut down all services
down:
    @echo "{{ MAGENTA }}Stopping containers...{{ NORMAL }}"
    @{{ COMPOSE }} down

# Restart a service (defaults to server)
restart service="server":
    @echo "{{ MAGENTA }}Restarting {{ service }}...{{ NORMAL }}"
    @{{ COMPOSE }} restart {{ service }}

# Tail container logs
logs *args:
    @{{ COMPOSE }} logs -f {{ args }}

# Open a bash shell in the Django container
shell:
    @{{ COMPOSE }} exec server bash

# Run a Django management command
manage *args:
    @{{ COMPOSE }} exec server python manage.py {{ args }}

# Run the test suite
test *args:
    @echo "{{ MAGENTA }}Running tests...{{ NORMAL }}"
    @{{ COMPOSE }} exec -e DJANGO_SETTINGS_MODULE=config.settings.test server python manage.py test {{ args }}

# Run pre-commit hooks on staged files
lint:
    @pre-commit run

# Run pre-commit hooks on all files
lint-all:
    @pre-commit run --all-files
