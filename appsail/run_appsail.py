# ChainC2 Sentinel — Zoho Catalyst AppSail Service Entrypoint
"""AppSail HTTP server launcher binding to the assigned Catalyst port."""

import http.server
import json
import logging
import os
import sys
from pathlib import Path

# Configure basic logging to stdout with immediate flush
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("chainc2_sentinel.appsail")

# Ensure workspace root and vendor directory are in sys.path
repo_root = Path(__file__).resolve().parent.parent
vendor_dir = Path(__file__).resolve().parent / "vendor"

if vendor_dir.exists() and str(vendor_dir) not in sys.path:
    sys.path.insert(0, str(vendor_dir))

if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))


def run_fallback_diagnostic_server(port: int, host: str, error_msg: str) -> None:
    """Run standard-library HTTP server to report environment diagnostics when dependencies fail."""
    logger.warning("Running standard-library diagnostic server due to import failure: %s", error_msg)

    class DiagnosticHandler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            data = {
                "status": "diagnostic_mode",
                "reason": error_msg,
                "python_version": sys.version,
                "cwd": os.getcwd(),
                "repo_root": str(repo_root),
                "sys_path": sys.path,
                "cwd_contents": os.listdir(".") if os.path.exists(".") else [],
                "port": port,
            }
            self.wfile.write(json.dumps(data, indent=2).encode("utf-8"))

        def log_message(self, format, *args):
            logger.info("Diagnostic request: " + format % args)

    server = http.server.HTTPServer((host, port), DiagnosticHandler)
    logger.info("Diagnostic server listening on %s:%d", host, port)
    sys.stdout.flush()
    server.serve_forever()


def main() -> None:
    port_raw = os.environ.get("X_ZOHO_CATALYST_LISTEN_PORT") or os.environ.get("PORT") or "5000"
    port = int(port_raw)
    host = "0.0.0.0"

    logger.info("=" * 70)
    logger.info("  ChainC2 Sentinel — Zoho Catalyst AppSail Service")
    logger.info("  Python: %s", sys.version)
    logger.info("  Repo Root: %s", repo_root)
    logger.info("  Vendor Dir: %s (exists=%s)", vendor_dir, vendor_dir.exists())
    logger.info("  Binding Host: %s:%d", host, port)
    logger.info("=" * 70)
    sys.stdout.flush()

    try:
        import flask
        import requests
        from src.dashboard.app import create_app

        app = create_app(repo_root=repo_root)
        logger.info("Flask application initialized successfully. Starting HTTP server on %s:%d...", host, port)
        sys.stdout.flush()
        app.run(host=host, port=port, debug=False)
    except Exception as exc:
        logger.error("Startup error in AppSail: %s", exc, exc_info=True)
        sys.stdout.flush()
        run_fallback_diagnostic_server(port=port, host=host, error_msg=str(exc))


if __name__ == "__main__":
    main()
