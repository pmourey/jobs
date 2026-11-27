#!/usr/bin/env python3
"""Point d'entrée MCP Stdio pour l'application Flask de suivi de candidatures."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
os.chdir(PROJECT_ROOT)
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Rediriger stdout vers stderr avant tout import applicatif afin qu'aucun log
# ou print parasite ne corrompe le protocole JSON-RPC sur stdio.
_REAL_STDOUT = sys.stdout
sys.stdout = sys.stderr

from flask_app import app  # noqa: E402
from tools.mcp_jobs import handle_mcp_message  # noqa: E402


def _resolve_user_id() -> int:
    raw = os.environ.get('JOBS_MCP_USER_ID') or str(app.config.get('MCP_USER_ID', 1))
    try:
        return int(raw)
    except (TypeError, ValueError):
        return 1


def main() -> int:
    user_id = _resolve_user_id()
    for raw_line in sys.stdin:
        line = raw_line.strip()
        if not line:
            continue
        try:
            message = json.loads(line)
        except json.JSONDecodeError as exc:
            err = {
                'jsonrpc': '2.0',
                'id': None,
                'error': {'code': -32700, 'message': f'Parse error: {exc}'},
            }
            _REAL_STDOUT.write(json.dumps(err, ensure_ascii=False) + '\n')
            _REAL_STDOUT.flush()
            continue

        if isinstance(message, list):
            responses = []
            for item in message:
                resp = handle_mcp_message(item, app=app, user_id=user_id)
                if resp is not None:
                    responses.append(resp)
            if responses:
                _REAL_STDOUT.write(json.dumps(responses, ensure_ascii=False) + '\n')
                _REAL_STDOUT.flush()
            continue

        response = handle_mcp_message(message, app=app, user_id=user_id)
        if response is not None:
            _REAL_STDOUT.write(json.dumps(response, ensure_ascii=False) + '\n')
            _REAL_STDOUT.flush()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
