#!/usr/bin/env bash
# Update an existing app/db Compose project after make container-check.
set -euo pipefail
umask 077

if [[ $# -ne 3 || -z "$1" || -z "$2" || -z "$3" ]]; then
    echo 'Usage: container_update.sh DOCKER ENV_FILE PROJECT' >&2
    exit 1
fi

# DOCKER is a command with simple space-separated arguments, e.g. sudo -n docker.
read -r -a docker_command <<< "$1"
env_file=$2
project=$3
[[ -f "$env_file" ]] || { echo 'Environment file not found' >&2; exit 1; }
[[ "$project" =~ ^[a-z0-9][a-z0-9_-]*$ ]] || { echo 'Invalid Compose project name' >&2; exit 1; }
compose=("${docker_command[@]}" compose --env-file "$env_file" -f compose.yaml -p "$project")

"${compose[@]}" config --quiet
db_id=$("${compose[@]}" ps -a -q db)
app_id=$("${compose[@]}" ps -a -q app)
for identifier in "$db_id" "$app_id"; do
    [[ -n "$identifier" && "$identifier" != *$'\n'* ]] || {
        echo 'Expected one existing app and one existing db; initial deployment is separate' >&2
        exit 1
    }
    state=$("${docker_command[@]}" inspect --format '{{.State.Status}}/{{if .State.Health}}{{.State.Health.Status}}{{end}}' "$identifier")
    [[ "$state" == running/healthy ]] || {
        echo 'Existing app and db must both be running and healthy before updating' >&2
        exit 1
    }
done

old_image=$("${docker_command[@]}" inspect --format '{{.Image}}' "$app_id")
"${compose[@]}" build app

mkdir -p backups
backup_dir=$(mktemp -d backups/container-update-XXXXXXXX)
printf '%s\n' "$old_image" > "$backup_dir/previous-app-image.txt"
printf '[container-update] Backup directory: %s\n' "$backup_dir"

on_error() {
    echo "CONTAINER_UPDATE_FAILED: application may be stopped; inspect $backup_dir" >&2
    echo 'A .partial file is not a confirmed backup. No automatic rollback was performed.' >&2
}
trap on_error ERR

# Quiesce this project's sole application before taking a database snapshot.
"${compose[@]}" stop app
"${compose[@]}" exec -T db sh -c \
    'exec pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc' \
    > "$backup_dir/postgres.dump.partial"
"${compose[@]}" exec -T db pg_restore --list \
    < "$backup_dir/postgres.dump.partial" > /dev/null
mv "$backup_dir/postgres.dump.partial" "$backup_dir/postgres.dump"
echo '[container-update] PostgreSQL archive created and readable'

"${compose[@]}" run --rm --no-deps -T app python manage.py migrate --noinput
"${compose[@]}" up -d --no-deps --no-build app
app_id=$("${compose[@]}" ps -a -q app)
deadline=$((SECONDS + 120))
while (( SECONDS < deadline )); do
    state=$(timeout 20s "${docker_command[@]}" inspect --format \
        '{{.State.Status}}/{{if .State.Health}}{{.State.Health.Status}}{{end}}' "$app_id")
    if [[ "$state" == running/healthy ]]; then
        "${compose[@]}" exec -T app python manage.py check
        "${compose[@]}" exec -T app python manage.py migrate --check
        trap - ERR
        echo "CONTAINER_UPDATE_OK: backup=$backup_dir/postgres.dump"
        exit 0
    fi
    sleep 2
done
echo 'Application did not become healthy within 120 seconds' >&2
on_error
exit 1
