#!/usr/bin/env bash

set -euo pipefail

# Delete preview projects older than MAX_AGE_HOURS.
# Matches projects whose name starts with PREVIEW_PROJECT_PREFIX.
# Safe to run on a schedule (e.g. daily cron in CI).

PREVIEW_PROJECT_PREFIX="${RAILWAY_PREVIEW_PROJECT_PREFIX:-agenta-oss-pr}"
MAX_AGE_HOURS="${RAILWAY_PREVIEW_MAX_AGE_HOURS:-24}"
DRY_RUN="${RAILWAY_PREVIEW_DRY_RUN:-false}"

if ! command -v railway >/dev/null 2>&1; then
    printf "Missing required command: railway\n" >&2
    exit 1
fi

if ! command -v jq >/dev/null 2>&1; then
    printf "Missing required command: jq\n" >&2
    exit 1
fi

if [ -z "${RAILWAY_API_TOKEN:-}" ] && [ -z "${RAILWAY_TOKEN:-}" ]; then
    railway whoami >/dev/null 2>&1 || {
        printf "Railway authentication is required. Set RAILWAY_API_TOKEN or run railway login.\n" >&2
        exit 1
    }
fi

NOW_EPOCH="$(date +%s)"
MAX_AGE_SECONDS=$((MAX_AGE_HOURS * 3600))
DELETED=0
SKIPPED=0

while IFS= read -r project; do
    name="$(printf "%s" "$project" | jq -r '.name')"
    created_at="$(printf "%s" "$project" | jq -r '.createdAt')"

    # Parse ISO 8601 timestamp to epoch seconds.
    created_epoch="$(date -d "$created_at" +%s 2>/dev/null || date -j -f "%Y-%m-%dT%H:%M:%S" "${created_at%%.*}" +%s 2>/dev/null || echo 0)"

    if [ "$created_epoch" -eq 0 ]; then
        printf "SKIP: %s (could not parse createdAt: %s)\n" "$name" "$created_at"
        SKIPPED=$((SKIPPED + 1))
        continue
    fi

    age_seconds=$((NOW_EPOCH - created_epoch))
    age_hours=$((age_seconds / 3600))

    if [ "$age_seconds" -gt "$MAX_AGE_SECONDS" ]; then
        if [ "$DRY_RUN" = "true" ]; then
            printf "DRY-RUN: would delete '%s' (age: %dh, created: %s)\n" "$name" "$age_hours" "$created_at"
        else
            printf "DELETE: '%s' (age: %dh, created: %s)\n" "$name" "$age_hours" "$created_at"
            railway delete --project "$name" --yes --json >/dev/null 2>&1 || {
                printf "  FAILED to delete '%s'\n" "$name" >&2
            }
        fi
        DELETED=$((DELETED + 1))
    else
        printf "KEEP: '%s' (age: %dh, max: %dh)\n" "$name" "$age_hours" "$MAX_AGE_HOURS"
        SKIPPED=$((SKIPPED + 1))
    fi
done < <(railway project list --json | jq -c --arg prefix "$PREVIEW_PROJECT_PREFIX" \
    '.[] | select(.name | startswith($prefix)) | {name: .name, createdAt: .createdAt}')

printf "Cleanup complete. Deleted: %d, Skipped: %d (prefix: %s, max age: %dh)\n" "$DELETED" "$SKIPPED" "$PREVIEW_PROJECT_PREFIX" "$MAX_AGE_HOURS"
