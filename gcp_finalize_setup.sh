#!/usr/bin/env bash
set -euo pipefail

# gcp_finalize_setup.sh
# Enables core Generative AI APIs (generativelanguage & aiplatform),
# ensures a service account exists, binds recommended roles and creates a JSON key.
# Usage:
#   ./gcp_finalize_setup.sh --project PROJECT_ID --sa SERVICE_ACCOUNT_EMAIL --key-path /path/to/key.json
# Example:
#   ./gcp_finalize_setup.sh --project suivi-candidatures --sa generative-ai-sa@suivi-candidatures.iam.gserviceaccount.com --key-path /Users/display/keys/generative-ai-sa.json

print_help(){
  cat <<'EOF'
Usage: gcp_finalize_setup.sh --project PROJECT_ID --sa SERVICE_ACCOUNT_EMAIL --key-path KEY_PATH

SERVICE_ACCOUNT_EMAIL must be the full service account email (e.g. generative-ai-sa@PROJECT_ID.iam.gserviceaccount.com)
EOF
}

PROJECT_ID=""
SA_EMAIL=""
KEY_PATH=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --project) PROJECT_ID="$2"; shift 2;;
    --sa) SA_EMAIL="$2"; shift 2;;
    --key-path) KEY_PATH="$2"; shift 2;;
    -h|--help) print_help; exit 0;;
    *) echo "Unknown arg: $1"; print_help; exit 1;;
  esac
done

if [[ -z "$PROJECT_ID" || -z "$SA_EMAIL" || -z "$KEY_PATH" ]]; then
  echo "Missing required args."; print_help; exit 1
fi

if ! command -v gcloud >/dev/null 2>&1; then
  echo "gcloud not found. Install Google Cloud SDK first."; exit 2
fi

echo "Project: $PROJECT_ID"
echo "Service Account: $SA_EMAIL"
echo "Key path: $KEY_PATH"

read -p "Continue? (y/N) " c
c_lc=$(echo "$c" | tr '[:upper:]' '[:lower:]')
if [[ "$c_lc" != "y" ]]; then
  echo "Aborted."; exit 0
fi

# Set project
gcloud config set project "$PROJECT_ID"

# Enable APIs (ignore gemini-specific which may not be available)
set +e
for svc in generativelanguage.googleapis.com aiplatform.googleapis.com; do
  echo "Enabling $svc..."
  gcloud services enable "$svc" --project="$PROJECT_ID" || echo "Warning: could not enable $svc (check permissions)."
done
set -e

# Check if SA exists
echo "Checking service account existence..."
if gcloud iam service-accounts describe "$SA_EMAIL" --project="$PROJECT_ID" >/dev/null 2>&1; then
  echo "Service account exists." 
else
  echo "Service account not found. Creating..."
  # attempt to infer local name from email
  SA_NAME=$(echo "$SA_EMAIL" | cut -d'@' -f1)
  gcloud iam service-accounts create "$SA_NAME" --display-name="Generative AI Service Account" --project="$PROJECT_ID"
fi

# Bind roles (may require owner permissions)
echo "Adding IAM policy bindings (may require permissions)..."
for role in roles/aiplatform.user roles/iam.serviceAccountUser; do
  echo "Binding $role to $SA_EMAIL"
  gcloud projects add-iam-policy-binding "$PROJECT_ID" \
    --member="serviceAccount:${SA_EMAIL}" \
    --role="$role" || echo "Warning: could not bind $role (insufficient permissions)."
done

# Create key
mkdir -p "$(dirname "$KEY_PATH")"
if [[ -f "$KEY_PATH" ]]; then
  read -p "Key file already exists at $KEY_PATH. Overwrite? (y/N) " ov
  ov_lc=$(echo "$ov" | tr '[:upper:]' '[:lower:]')
  if [[ "$ov_lc" != "y" ]]; then
    echo "Skipping key creation."; exit 0
  fi
  rm -f "$KEY_PATH"
fi

echo "Creating key at $KEY_PATH"
gcloud iam service-accounts keys create "$KEY_PATH" \
  --iam-account="$SA_EMAIL" \
  --project="$PROJECT_ID" || { echo "Failed to create key (permission denied or other error)."; exit 2; }

echo "Key created. Ensure you export: export GOOGLE_APPLICATION_CREDENTIALS=\"$KEY_PATH\""

echo "Done."