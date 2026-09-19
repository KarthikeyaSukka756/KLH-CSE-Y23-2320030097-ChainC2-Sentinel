"""ChainC2 Sentinel — WSGI & Vercel Application Entrypoint.

Exposes module-level Flask WSGI instance `app` for deployment and local execution.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure both repository root and src directory are in Python search path
_src_dir = Path(__file__).resolve().parent
_repo_root = _src_dir.parent

for _p in (str(_repo_root), str(_src_dir)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

try:
    from src.dashboard.app import create_app
except ImportError:
    from dashboard.app import create_app

app = create_app(repo_root=_repo_root)

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=False)