#!/usr/bin/env bash
set -euo pipefail

# gcp_enable_and_bind.sh
# Enables Generative AI APIs, ensures service account exists, binds roles and creates a key.
# Usage:
#   ./gcp_enable_and_bind.sh --project PROJECT_ID --sa-email SERVICE_ACCOUNT_EMAIL --key-path /path/to/key.json

print_help(){
  cat <<'EOF'
Usage: gcp_enable_and_bind.sh --project PROJECT_ID --sa-email SERVICE_ACCOUNT_EMAIL --key-path KEY_PATH

Example:
  ./gcp_enable_and_bind.sh --project suivi-candidatures --sa-email generative-ai-sa@suivi-candidatures.iam.gserviceaccount.com --key-path /Users/display/keys/generative-ai-sa.json
EOF
}

PROJECT_ID=""
SA_EMAIL=""
KEY_PATH=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --project) PROJECT_ID="$2"; shift 2;;
    --sa-email) SA_EMAIL="$2"; shift 2;;
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

export PROJECT_ID

echo "Setting gcloud project to $PROJECT_ID"
gcloud config set project "$PROJECT_ID"

# Enable APIs
for svc in generativelanguage.googleapis.com aiplatform.googleapis.com; do
  echo "Enabling $svc..."
  gcloud services enable "$svc" --project="$PROJECT_ID" || echo "Warning: could not enable $svc (check permissions)."
done

# Ensure SA exists
if gcloud iam service-accounts describe "$SA_EMAIL" --project="$PROJECT_ID" >/dev/null 2>&1; then
  echo "Service account $SA_EMAIL exists."
else
  echo "Service account not found. Creating..."
  SA_NAME=$(echo "$SA_EMAIL" | cut -d'@' -f1)
  gcloud iam service-accounts create "$SA_NAME" --display-name="Generative AI SA" --project="$PROJECT_ID"
fi

# Bind roles
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
  --iam-account="$SA_EMAIL" --project="$PROJECT_ID" || { echo "Failed to create key."; exit 2; }

export GOOGLE_APPLICATION_CREDENTIALS="$KEY_PATH"

echo "Key created and GOOGLE_APPLICATION_CREDENTIALS exported for this session."

echo "To verify, run the python token+models check provided in the README or use the list_models.py script."

echo "Done."
