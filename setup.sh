#!/usr/bin/env bash
set -euo pipefail
umask 077

die() {
    printf 'Error: %s\n' "$1" >&2
    exit 1
}

command -v docker >/dev/null || die "docker is required"
command -v openssl >/dev/null || die "openssl is required"
command -v curl >/dev/null || die "curl is required"
docker compose version >/dev/null 2>&1 || die "Docker Compose v2 is required"
docker info >/dev/null 2>&1 || die "Docker is not running"
[ -f .env.example ] || die ".env.example is missing"

[ -f .env ] || cp .env.example .env

backend_port=${BACKEND_PORT:-8000}
frontend_port=${FRONTEND_PORT:-3000}

env_value() {
    awk -F= -v key="$1" '$1 == key { sub(/^[^=]*=/, ""); print; exit }' .env
}

set_env_value() {
    local key="$1" value="$2" tmp
    tmp=$(mktemp)
    awk -F= -v key="$key" '$1 != key' .env > "$tmp"
    printf '%s=%s\n' "$key" "$value" >> "$tmp"
    mv "$tmp" .env
}

api_key=${OPENAI_API_KEY:-$(env_value OPENAI_API_KEY)}
if [ -z "$api_key" ] || [ "$api_key" = "your_openai_api_key_here" ]; then
    read -r -s -p "OpenAI API key: " api_key
    printf '\n'
fi
[ -n "$api_key" ] || die "OPENAI_API_KEY is required"
set_env_value OPENAI_API_KEY "$api_key"

ensure_secret() {
    local key="$1" value
    value=$(env_value "$key")
    case "$value" in
        ""|REPLACE_*|CHANGE_*|YOUR_*|your_*)
            value=$(openssl rand -hex 32)
            set_env_value "$key" "$value"
            ;;
    esac
    printf '%s' "$value"
}

jwt_secret=$(ensure_secret JWT_SECRET)
postgres_password=$(ensure_secret POSTGRES_PASSWORD)
[ "${#jwt_secret}" -ge 32 ] || die "JWT_SECRET must be at least 32 characters"
[ "${#postgres_password}" -ge 32 ] || die "POSTGRES_PASSWORD must be at least 32 characters"
chmod 600 .env

docker compose up -d --build

wait_for() {
    local label="$1"
    shift
    local deadline=$((SECONDS + 300))
    until "$@" >/dev/null 2>&1; do
        if (( SECONDS >= deadline )); then
            printf 'Error: %s was not ready within 300 seconds.\n' "$label" >&2
            docker compose ps || true
            printf 'Inspect logs: docker compose logs %s\n' "$label" >&2
            return 1
        fi
        sleep 2
    done
}

wait_for clamav docker compose exec -T backend curl -fsS http://clamav:8000/health
wait_for backend curl -fsS "http://localhost:${backend_port}/api/health"
wait_for frontend curl -fsS "http://localhost:${frontend_port}"

printf 'Ready: frontend http://localhost:%s, API http://localhost:%s\n' "$frontend_port" "$backend_port"
