#!/usr/bin/env bash
# Download Kokoro-82M model + voices (hexgrad/Kokoro-82M) using curl.
# Expected checksums live in Kokoro-82M.md5 (next to this script):
#   <md5>  <relative-path>
# Each file is downloaded only if missing or if its md5 doesn't match.
set -euo pipefail

REPO="hexgrad/Kokoro-82M"
BASE="https://huggingface.co/${REPO}/resolve/main"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MANIFEST="${SCRIPT_DIR}/Kokoro-82M.md5"
MODEL_DIR="${SCRIPT_DIR}/Kokoro-82M"
OUT_DIR="${SCRIPT_DIR}/output"

if [ ! -f "${MANIFEST}" ]; then
  echo "ERROR: manifest not found at ${MANIFEST}" >&2
  exit 1
fi

mkdir -p "${OUT_DIR}"

ok() {
  # ok <relpath> -> 0 if file exists with matching md5
  local rel="$1"
  local target="${MODEL_DIR}/${rel}"
  local want got
  want="$(awk -v p="${rel}" '$2==p {print $1}' "${MANIFEST}")"
  if [ -z "${want}" ] || [ ! -f "${target}" ]; then return 1; fi
  got="$(md5 -q "${target}" 2>/dev/null || true)"
  [ "${got}" = "${want}" ]
}

download() {
  # download <relpath> -> fetch to temp file, verify md5, then install
  local rel="$1"
  local target="${MODEL_DIR}/${rel}"
  local tmp="${target}.tmp"
  local want
  want="$(awk -v p="${rel}" '$2==p {print $1}' "${MANIFEST}")"
  mkdir -p "$(dirname "${target}")"
  echo "get    ${rel}"
  rm -f "${tmp}"
  /usr/bin/curl -fsSL -o "${tmp}" "${BASE}/${rel}"
  if [ "$(md5 -q "${tmp}" 2>/dev/null || true)" != "${want}" ]; then
    echo "ERROR: md5 mismatch for ${rel} (want ${want})" >&2
    rm -f "${tmp}"
    exit 1
  fi
  mv "${tmp}" "${target}"
}

count=0
while read -r want rel; do
  if ok "${rel}"; then
    continue
  fi
  download "${rel}"
  count=$((count + 1))
done < "${MANIFEST}"

VOICE_COUNT="$(find "${MODEL_DIR}/voices" -name '*.pt' | wc -l | tr -d ' ')"
echo "Done. Downloaded ${count} file(s); ${VOICE_COUNT} voices verified in ${MODEL_DIR}"
echo "Output dir: ${OUT_DIR}"
