#!/usr/bin/env python3
"""Static dev server for the Aijolot frontend with caching disabled.

The frontend is plain JSX compiled in-browser by Babel standalone. The stock
`python -m http.server` sends no Cache-Control header, so browsers heuristically
cache the `.jsx` files and serve stale code after edits. This server sends
`Cache-Control: no-store` so a normal reload always fetches the latest source.

Usage: python3 scripts/dev-frontend.py [port]   (default 5500, serves ./frontend)
"""

from __future__ import annotations

import http.server
import os
import socketserver
import sys
from pathlib import Path

PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 5500
FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"


class NoCacheHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(FRONTEND_DIR), **kwargs)

    def end_headers(self):
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0")
        self.send_header("Pragma", "no-cache")
        self.send_header("Expires", "0")
        super().end_headers()

    def log_message(self, *args):  # quieter logs
        pass


if __name__ == "__main__":
    os.chdir(FRONTEND_DIR)
    with socketserver.TCPServer(("127.0.0.1", PORT), NoCacheHandler) as httpd:
        print(f"Aijolot frontend (no-cache) on http://127.0.0.1:{PORT}  serving {FRONTEND_DIR}")
        httpd.serve_forever()
