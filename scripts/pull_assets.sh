#!/usr/bin/env bash
# Pre-warm the Hugging Face cache with the GR00T model. Safe to re-run; the
# CLI skips already-downloaded files.
set -euo pipefail

: "${HF_TOKEN:?HF_TOKEN must be set (see .env.example)}"

HF_CACHE="${HF_CACHE:-${HOME}/.cache/huggingface}"
TARGET="${HF_CACHE}/nvidia/GR00T-N1.7-3B"

mkdir -p "${TARGET}"

huggingface-cli download nvidia/GR00T-N1.7-3B --local-dir "${TARGET}" --token "${HF_TOKEN}"
