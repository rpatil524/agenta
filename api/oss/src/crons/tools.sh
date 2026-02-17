#!/bin/sh
set -eu

# Only run if Composio is configured
COMPOSIO_API_KEY=$(tr '\0' '\n' < /proc/1/environ | grep ^COMPOSIO_API_KEY= | cut -d= -f2- || true)
if [ -z "$COMPOSIO_API_KEY" ]; then
    echo "[$(date)] Skipping tools catalog refresh - COMPOSIO_API_KEY not set" >> /proc/1/fd/1
    exit 0
fi

AGENTA_AUTH_KEY=$(tr '\0' '\n' < /proc/1/environ | grep ^AGENTA_AUTH_KEY= | cut -d= -f2- || true)
AGENTA_AUTH_KEY="${AGENTA_AUTH_KEY:-replace-me}"

echo "--------------------------------------------------------"
echo "[$(date)] tools.sh running from cron" >> /proc/1/fd/1

# Warm the catalog cache by calling admin refresh endpoint
# This populates cache for: providers -> integrations -> actions (with full schemas)
echo "[$(date)] Refreshing catalog cache..." >> /proc/1/fd/1
curl \
    -s \
    -w "\nHTTP_STATUS:%{http_code}\n" \
    -X POST \
    -H "Authorization: Access ${AGENTA_AUTH_KEY}" \
    "http://api:8000/api/preview/tools/admin/catalog/refresh" || echo "❌ CURL failed"

echo "[$(date)] tools.sh done" >> /proc/1/fd/1
