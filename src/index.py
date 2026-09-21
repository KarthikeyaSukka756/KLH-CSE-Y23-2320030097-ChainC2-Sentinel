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

import urllib.parse

try:
    from src.dashboard.app import create_app
except ImportError:
    from dashboard.app import create_app


class VercelPathFixMiddleware:
    """WSGI Middleware for Vercel Serverless Function deployments.

    Restores the true requested path into WSGI PATH_INFO from:
    1. Query parameter `__vercel_path` passed by vercel.json rewrite
    2. HTTP_X_MATCHED_PATH / HTTP_X_FORWARDED_URI headers
    while preserving other query parameters.
    """

    def __init__(self, wsgi_app):
        self.wsgi_app = wsgi_app

    def __call__(self, environ, start_response):
        path = environ.get("PATH_INFO", "")
        query = environ.get("QUERY_STRING", "")

        # Check if incoming PATH_INFO points to entrypoint itself or is empty
        if path in ("/src/index.py", "/src/index", "/index.py", "/index", ""):
            if "__vercel_path=" in query:
                params = urllib.parse.parse_qs(query, keep_blank_values=True)
                if "__vercel_path" in params:
                    vpath = params.pop("__vercel_path")[0]
                    if not vpath.startswith("/"):
                        vpath = "/" + vpath
                    environ["PATH_INFO"] = vpath
                    # Reconstruct clean QUERY_STRING without __vercel_path
                    new_q = []
                    for k, vals in params.items():
                        for v in vals:
                            new_q.append(f"{urllib.parse.quote(k)}={urllib.parse.quote(v)}")
                    environ["QUERY_STRING"] = "&".join(new_q)
            elif environ.get("HTTP_X_MATCHED_PATH") and environ["HTTP_X_MATCHED_PATH"] not in ("/src/index.py", "/src/index"):
                environ["PATH_INFO"] = environ["HTTP_X_MATCHED_PATH"]
            elif environ.get("HTTP_X_FORWARDED_URI"):
                fwd = environ["HTTP_X_FORWARDED_URI"].split("?")[0]
                environ["PATH_INFO"] = fwd
            else:
                environ["PATH_INFO"] = "/"

        return self.wsgi_app(environ, start_response)


app = create_app(repo_root=_repo_root)
app.wsgi_app = VercelPathFixMiddleware(app.wsgi_app)

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=False)