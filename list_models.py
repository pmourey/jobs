"""List available Generative Language models for the current project using ADC.

Usage:

export GOOGLE_APPLICATION_CREDENTIALS=/path/to/key.json
python list_models.py

This script prints HTTP status and response body (truncated).
"""
import os
import sys

try:
    import google.auth
    import google.auth.transport.requests
    import requests
except Exception as e:
    print('Missing dependencies. Install with: pip install google-auth requests')
    raise


def main():
    creds_path = os.environ.get('GOOGLE_APPLICATION_CREDENTIALS')
    if not creds_path or not os.path.exists(creds_path):
        print('ERROR: GOOGLE_APPLICATION_CREDENTIALS not set or file not found.\nSet export GOOGLE_APPLICATION_CREDENTIALS=/path/to/key.json')
        sys.exit(2)
    # Prefer explicit service account loading with cloud-platform scope to ensure token has required scopes
    sac_path = os.environ.get('GOOGLE_APPLICATION_CREDENTIALS')
    try:
        from google.oauth2 import service_account
        if sac_path and os.path.exists(sac_path):
            creds = service_account.Credentials.from_service_account_file(sac_path, scopes=['https://www.googleapis.com/auth/cloud-platform'])
        else:
            creds, project = google.auth.default(scopes=['https://www.googleapis.com/auth/cloud-platform'])
    except Exception:
        creds, project = google.auth.default(scopes=['https://www.googleapis.com/auth/cloud-platform'])

    auth_req = google.auth.transport.requests.Request()
    creds.refresh(auth_req)
    token = creds.token
    headers = {'Authorization': f'Bearer {token}'}
    url = 'https://generativelanguage.googleapis.com/v1/models'
    print('Calling', url)
    resp = requests.get(url, headers=headers, timeout=30)
    print('Status:', resp.status_code)
    text = resp.text
    try:
        print(text)
    except Exception:
        print(text[:2000])


if __name__ == '__main__':
    main()
