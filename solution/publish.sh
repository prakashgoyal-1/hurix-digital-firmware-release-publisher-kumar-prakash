#!/usr/bin/env bash

set -euo pipefail

SOURCE="/solution/release-publisher.mjs"

DIR="/app/publisher"

TARGET="${DIR}/release-publisher.mjs"

if [[ ! -f "${SOURCE}" ]]; then

  echo "Reference publisher not found: ${SOURCE}" >&2

  exit 1
  
fi

mkdir -p "${DIR}"

cp "${SOURCE}" "${TARGET}"

chmod 0644 "${TARGET}"

echo "Installed reference publisher at ${TARGET}" >&2