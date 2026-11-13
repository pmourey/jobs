"""Test script: verify Google Generative AI (Gemini) access using ADC.

Usage (after creating service account key):

export GOOGLE_APPLICATION_CREDENTIALS=/path/to/key.json
pip install --upgrade google-generative-ai google-auth
python test_google_api.py

The script prints a short response or an error for debugging.
"""
import os
import sys

# Try to use python client if available, otherwise fallback to REST using ADC tokens.
MODEL = os.environ.get('GCP_TEST_MODEL', 'models/text-bison-001')
# normalize model: allow values like 'models/text-bison-001' or 'text-bison-001'
if MODEL.startswith('models/'):
    MODEL = MODEL.split('/', 1)[1]

PROMPT = 'Bonjour. Ceci est un test de connexion. Répondez en une phrase en français.'


def _call_via_client():
    # Try new client first (google.genai), then deprecated google.generativeai
    try:
        import google.genai as genai
        try:
            # google.genai client: GenAI SDK
            client = genai.GenerativeAI()
            # attempt simple text generation; API may differ by version
            try:
                resp = client.generate_text(model=MODEL, prompt=PROMPT, max_output_tokens=64)
                # resp may have .text or be dict-like
                text = getattr(resp, 'text', None) or (resp.get('candidates', [{}])[0].get('content') if isinstance(resp, dict) else None)
                if text:
                    return text
            except Exception:
                # try alternative call signature
                resp = genai.generate_text(model=MODEL, prompt=PROMPT, max_output_tokens=64)
                text = getattr(resp, 'text', None) or (resp.get('candidates', [{}])[0].get('content') if isinstance(resp, dict) else None)
                if text:
                    return text
        except Exception:
            pass
    except Exception:
        pass

    try:
        import google.generativeai as genai_old
    except Exception:
        return None
    try:
        genai_old.configure()
        resp = genai_old.models.generate_text(model=MODEL, prompt=PROMPT, max_output_tokens=64)
        text = getattr(resp, 'text', None)
        if not text and isinstance(resp, dict):
            text = resp.get('candidates', [{}])[0].get('content') or resp.get('output') or resp.get('text')
        return text
    except Exception:
        return None


def _call_via_rest():
    # Use google-auth ADC to get bearer token and call REST endpoint
    try:
        import google.auth
        import google.auth.transport.requests
        import requests
    except Exception as e:
        print('Missing dependencies for REST fallback. Install: pip install google-auth requests')
        raise

    creds, project = google.auth.default(scopes=['https://www.googleapis.com/auth/cloud-platform'])
    auth_req = google.auth.transport.requests.Request()
    creds.refresh(auth_req)
    token = creds.token
    if not token:
        raise RuntimeError('Failed to obtain access token via ADC')

    endpoint = f'https://generativelanguage.googleapis.com/v1/models/{MODEL}:generateText'
    headers = {'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'}
    payload = {'prompt': PROMPT, 'maxOutputTokens': 64, 'temperature': 0.2}
    resp = requests.post(endpoint, json=payload, headers=headers, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    # extract text from common fields
    if isinstance(data, dict):
        if 'candidates' in data and data['candidates']:
            return data['candidates'][0].get('content') or ''
        return data.get('output') or data.get('text') or ''
    return str(data)


def main():
    creds_path = os.environ.get('GOOGLE_APPLICATION_CREDENTIALS')
    if not creds_path or not os.path.exists(creds_path):
        print('ERROR: GOOGLE_APPLICATION_CREDENTIALS not set or file not found.\nSet export GOOGLE_APPLICATION_CREDENTIALS=/path/to/key.json')
        sys.exit(2)
    print('Using credentials:', creds_path)

    # Try client first
    text = _call_via_client()
    if text:
        print('Response (client):')
        print(text)
        return

    # Fallback to REST
    try:
        print('Client not available or failed — trying REST via ADC...')
        text = _call_via_rest()
        print('Response (REST):')
        print(text)
    except Exception as exc:
        print('API call failed:')
        print(exc)
        sys.exit(3)


if __name__ == '__main__':
    import os
    import sys
    main()
