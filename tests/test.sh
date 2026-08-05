#!/usr/bin/env bash

set -Eeuo pipefail

LOG_DIR="/logs/verifier"
REWARD_FILE="${LOG_DIR}/reward.txt"
GATEWAY_LOG="${LOG_DIR}/gateway.log"

GATEWAY_DATA_DIR="${LOG_DIR}/gateway-data"

CTRF_FILE="${LOG_DIR}/ctrf.json"
TEST_FILE="/tests/test_outputs.py"

PUBLISHER_DB="/app/releases.duckdb"
GATEWAY_SERVER="/app/distribution-gateway/server.js"

GATEWAY_URL="http://127.0.0.1:7070/healthz"


mkdir -p "${LOG_DIR}"


# Failure = default result
printf '0\n' > "${REWARD_FILE}"

rm -f "${PUBLISHER_DB}" "${PUBLISHER_DB}.wal" "${CTRF_FILE}" "${GATEWAY_LOG}"
rm -rf "${GATEWAY_DATA_DIR}"

mkdir -p "${GATEWAY_DATA_DIR}"

GATEWAY_PID=""


cleanup() {
    if [[ -n "${GATEWAY_PID}" ]] && kill -0 "${GATEWAY_PID}" 2>/dev/null; then
      kill "${GATEWAY_PID}" 2>/dev/null || true
      wait "${GATEWAY_PID}" 2>/dev/null || true

    fi

    rm -rf "${GATEWAY_DATA_DIR}"
}

trap cleanup EXIT


# Start provided distribution gateway
GATEWAY_DATA_DIR="${GATEWAY_DATA_DIR}" node "${GATEWAY_SERVER}" > "${GATEWAY_LOG}" 2>&1 &

GATEWAY_PID=$!

gateway_ready=0


for attempt in {1..50}; do
    # Stop waiting if gateway crashed already.
    if ! kill -0 "${GATEWAY_PID}" 2>/dev/null; then
        break

    fi


    if node -e "fetch('${GATEWAY_URL}').then(response => process.exit(response.ok ? 0 : 1)).catch(() => process.exit(1));"; then
        gateway_ready=1

        break
    fi

    sleep 0.2

done


if [[ "${gateway_ready}" -ne 1 ]]; then
    echo "Gateway did not become ready." >&2
    echo "Gateway log:" >&2

    cat "${GATEWAY_LOG}" >&2 || true

    exit 2
fi


cd /app


if python3 -m pytest --ctrf "${CTRF_FILE}" "${TEST_FILE}" -rA; then
    pytest_code=0

else
    pytest_code=$?

fi


echo "pytest exit code: ${pytest_code}"


if [[ "${pytest_code}" -eq 0 ]];  then
    printf '1\n' > "${REWARD_FILE}"

else
    printf '0\n' > "${REWARD_FILE}"

fi


exit "${pytest_code}"