#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$REPO_ROOT"

PORT="${FINORA_DEMO_PORT:-8000}"
BASE_URL="http://127.0.0.1:${PORT}"

echo "Starting FINORA API on ${BASE_URL}"
python -m uvicorn aurum.api.main:app --host 127.0.0.1 --port "$PORT" >/tmp/finora-demo-api.log 2>&1 &
API_PID="$!"

cleanup() {
  if kill -0 "$API_PID" >/dev/null 2>&1; then
    kill "$API_PID"
  fi
}
trap cleanup EXIT

for _ in $(seq 1 30); do
  if curl -fsS "${BASE_URL}/health" >/tmp/finora-health.json; then
    break
  fi
  sleep 1
done

echo
echo "Health"
cat /tmp/finora-health.json
echo

FORECAST_PAYLOAD='{
  "target": "DEMO",
  "values": [
    100.0, 100.8, 101.2, 100.9, 101.7,
    102.4, 102.1, 102.9, 103.5, 103.1,
    104.0, 104.6, 104.2, 105.0, 105.7,
    106.1, 105.8, 106.6, 107.2, 107.8,
    108.1, 108.7, 109.3, 109.0, 109.8
  ],
  "dates": [
    "2026-01-01", "2026-01-02", "2026-01-03", "2026-01-04", "2026-01-05",
    "2026-01-06", "2026-01-07", "2026-01-08", "2026-01-09", "2026-01-10",
    "2026-01-11", "2026-01-12", "2026-01-13", "2026-01-14", "2026-01-15",
    "2026-01-16", "2026-01-17", "2026-01-18", "2026-01-19", "2026-01-20",
    "2026-01-21", "2026-01-22", "2026-01-23", "2026-01-24", "2026-01-25"
  ],
  "horizon": 3,
  "frequency": "daily",
  "forecast_start": "2026-01-26T00:00:00Z"
}'

echo
echo "Forecast"
curl -fsS -X POST "${BASE_URL}/v1/forecast" \
  -H "Content-Type: application/json" \
  -d "$FORECAST_PAYLOAD"
echo

echo
echo "Sentiment"
curl -fsS -X POST "${BASE_URL}/v1/sentiment" \
  -H "Content-Type: application/json" \
  -d '{"text":"Revenue growth was strong, but management warned about margin pressure."}'
echo

echo
echo "Audit status"
curl -fsS "${BASE_URL}/health"
echo
