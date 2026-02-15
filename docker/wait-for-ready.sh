#!/usr/bin/env bash
# Wait for Lidarr to be healthy, then extract the API key.
set -euo pipefail

MAX_WAIT=120
CONTAINER="lidarr-test"

echo "Waiting for Lidarr to be healthy..."
for i in $(seq 1 "$MAX_WAIT"); do
    status=$(docker inspect --format='{{.State.Health.Status}}' "$CONTAINER" 2>/dev/null || echo "not_found")
    if [ "$status" = "healthy" ]; then
        echo "Lidarr is healthy after ${i}s"

        # Ensure volume directories are writable by the Lidarr user
        docker exec "$CONTAINER" chmod 777 /music /downloads 2>/dev/null || true

        # Extract API key from config.xml
        API_KEY=$(docker exec "$CONTAINER" cat /config/config.xml | grep -oP '(?<=<ApiKey>)[^<]+')
        echo "API Key: $API_KEY"
        echo ""
        echo "Set environment:"
        echo "  export LIDARR_URL=http://localhost:8686"
        echo "  export LIDARR_API_KEY=$API_KEY"
        exit 0
    fi
    sleep 1
done

echo "Lidarr failed to become healthy within ${MAX_WAIT}s"
exit 1
