#!/usr/bin/env bash
set -euo pipefail

die() {
    printf 'Error: %s\n' "$1" >&2
    exit 1
}

api_url=${API_URL:-http://localhost:${BACKEND_PORT:-8000}}
job_file=examples/synthetic-job-description.txt
cv_file=examples/synthetic-cv.pdf

[ -f "$job_file" ] || die "Missing synthetic fixture: $job_file (created by Task 5)"
[ -f "$cv_file" ] || die "Missing synthetic fixture: $cv_file (created by Task 5)"
command -v docker >/dev/null || die "docker is required"
command -v curl >/dev/null || die "curl is required"
docker compose version >/dev/null 2>&1 || die "Docker Compose v2 is required"

guest_token=$(docker compose exec -T backend python -c 'import uuid; print(uuid.uuid4())')
job_payload=$(docker compose exec -T backend python -c \
    'import json,sys; print(json.dumps({"job_text": sys.stdin.read(), "is_public": False}))' \
    < "$job_file")
job_response=$(curl -fsS -H "X-Guest-Token: $guest_token" \
    -H 'Content-Type: application/json' --data-binary "$job_payload" \
    "$api_url/api/jobs")
job_id=$(printf '%s' "$job_response" | docker compose exec -T backend python -c \
    'import json,sys; print(json.load(sys.stdin)["job_id"])')

cv_response=$(curl -fsS -H "X-Guest-Token: $guest_token" \
    -F "file=@$cv_file;type=application/pdf" "$api_url/api/cvs")
printf '%s' "$cv_response" | docker compose exec -T backend python -c \
    'import json,sys; assert json.load(sys.stdin).get("cv_id")' >/dev/null

screening_response=$(curl -fsS -H "X-Guest-Token: $guest_token" \
    -H 'Content-Type: application/json' \
    --data-binary '{"job_id":"'"$job_id"'","top_k":10,"owner_only":true}' \
    "$api_url/api/screening")
if ! candidate_count=$(printf '%s' "$screening_response" | \
    docker compose exec -T backend python -c \
    'import json,sys
data = json.load(sys.stdin)
candidates = data.get("candidates") if isinstance(data, dict) else None
if not isinstance(data, dict) or data.get("job_id") != sys.argv[1] or not isinstance(candidates, list) or not candidates:
    raise SystemExit(1)
print(len(candidates))' "$job_id"); then
    die "Screening did not complete with at least one candidate"
fi

printf 'Smoke completed with %s candidate(s).\n' "$candidate_count"
