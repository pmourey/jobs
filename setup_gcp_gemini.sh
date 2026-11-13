#!/usr/bin/env bash
set -euo pipefail

# setup_gcp_gemini.sh
# Automates GCP service account creation and API enabling for Generative AI (Gemini).
# Usage: ./setup_gcp_gemini.sh --project PROJECT_ID --sa SERVICE_ACCOUNT_NAME --key-path /path/to/key.json

print_help(){
  cat <<'EOF'
Usage: setup_gcp_gemini.sh --project PROJECT_ID --sa SERVICE_ACCOUNT_NAME --key-path KEY_PATH

Example:
  ./setup_gcp_gemini.sh --project suivi-candidatures --sa generative-ai-sa --key-path /Users/display/keys/generative-ai-sa.json

This script will:
 - check that gcloud is installed and authenticated
 - enable recommended APIs
 - create a service account
 - assign roles/aiplatform.user and iam.serviceAccountUser
 - create a JSON key at KEY_PATH

It will NOT commit any secrets to git. Keep the key safe.
EOF
}

PROJECT_ID=""
SA=""
KEY_PATH=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --project) PROJECT_ID="$2"; shift 2;;
    --sa) SA="$2"; shift 2;;
    --key-path) KEY_PATH="$2"; shift 2;;
    -h|--help) print_help; exit 0;;
    *) echo "Unknown arg: $1"; print_help; exit 1;;
  esac
done

if [[ -z "$PROJECT_ID" || -z "$SA" || -z "$KEY_PATH" ]]; then
  echo "Missing required args."; print_help; exit 1
fi

if ! command -v gcloud >/dev/null 2>&1; then
  echo "gcloud not found. Install Google Cloud SDK first: https://cloud.google.com/sdk/docs/install"
  exit 2
fi

echo "Using PROJECT_ID=$PROJECT_ID, SERVICE_ACCOUNT=$SA, KEY_PATH=$KEY_PATH"
read -p "Continue? (y/N) " confirm
confirm_lc=$(echo "$confirm" | tr '[:upper:]' '[:lower:]')
if [[ "$confirm_lc" != "y" ]]; then
  echo "Aborted by user."; exit 0
fi

# Ensure user is logged in and project is set
echo "Checking gcloud authentication and project..."
gcloud auth list --filter=status:ACTIVE --format="value(account)" || true
CURRENT_PROJECT=$(gcloud config get-value project 2>/dev/null || echo "")
if [[ "$CURRENT_PROJECT" != "$PROJECT_ID" ]]; then
  echo "Setting gcloud project to $PROJECT_ID"
  gcloud config set project "$PROJECT_ID"
fi

echo "Enabling APIs (may require permissions)..."
# Try enabling common candidate APIs; ignore errors for unknown services
set +e
gcloud services enable generativelanguage.googleapis.com --project="$PROJECT_ID"
gcloud services enable aiplatform.googleapis.com --project="$PROJECT_ID"
gcloud services enable gemini-enterprise-agent.googleapis.com --project="$PROJECT_ID" || true
set -e

# Create service account
echo "Creating service account: $SA"
gcloud iam service-accounts create "$SA" \
  --display-name="Generative AI Service Account" \
  --project="$PROJECT_ID"

SA_EMAIL="${SA}@${PROJECT_ID}.iam.gserviceaccount.com"

echo "Granting roles: roles/aiplatform.user and roles/iam.serviceAccountUser to $SA_EMAIL"
gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member="serviceAccount:${SA_EMAIL}" \
  --role="roles/aiplatform.user"

gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member="serviceAccount:${SA_EMAIL}" \
  --role="roles/iam.serviceAccountUser"

# Create key
mkdir -p "$(dirname "$KEY_PATH")"
if [[ -f "$KEY_PATH" ]]; then
  read -p "Key file already exists at $KEY_PATH. Overwrite? (y/N) " ov
  ov_lc=$(echo "$ov" | tr '[:upper:]' '[:lower:]')
  if [[ "$ov_lc" != "y" ]]; then
    echo "Aborting to avoid overwriting existing key."; exit 0
  fi
  rm -f "$KEY_PATH"
fi

echo "Creating service account key at $KEY_PATH"
gcloud iam service-accounts keys create "$KEY_PATH" \
  --iam-account="$SA_EMAIL" \
  --project="$PROJECT_ID"

echo "Key created. Please secure the file and do NOT commit it to source control."

echo "Exporting GOOGLE_APPLICATION_CREDENTIALS for this session (not persisted)"
export GOOGLE_APPLICATION_CREDENTIALS="$KEY_PATH"

echo "Done. Test with: export GOOGLE_APPLICATION_CREDENTIALS=\"$KEY_PATH\" && python -c \"import google.generativeai as genai; genai.configure(); print('ok')\""

exit 0
