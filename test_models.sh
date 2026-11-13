#!/usr/bin/env bash
set -euo pipefail

# Make script executable when created


# test_models.sh
# Iterates through common model names and calls test_google_api.py using ADC key.

export GOOGLE_APPLICATION_CREDENTIALS="/Users/display/keys/generative-ai-sa.json"

MODELS=(
  "models/text-bison-001"
  "text-bison-001"
  "models/chat-bison-001"
  "chat-bison-001"
  "text-bison@001"
  "chat-bison@001"
)

for m in "${MODELS[@]}"; do
  echo "Trying: $m"
  export GCP_TEST_MODEL="$m"
  python test_google_api.py || true
  echo "---"
done
