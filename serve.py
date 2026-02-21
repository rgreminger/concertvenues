#!/usr/bin/env python3
"""Serve the generated static site locally for preview."""

import http.server
import os
import socketserver
import webbrowser
from pathlib import Path

PORT = 8000
OUTPUT_DIR = Path("output")


class Handler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, format, *args):
        # Suppress default per-request logging; print a cleaner version
        print(f"  {self.command} {self.path}")


def main():
    if not OUTPUT_DIR.exists() or not any(OUTPUT_DIR.iterdir()):
        print(f"'{OUTPUT_DIR}' is empty or missing. Run 'cv generate' first.")
        return

    os.chdir(OUTPUT_DIR)

    url = f"http://localhost:{PORT}"
    print(f"Serving '{OUTPUT_DIR}/' at {url}")
    print("Press Ctrl+C to stop.\n")
    webbrowser.open(url)

    with socketserver.TCPServer(("", PORT), Handler) as httpd:
        httpd.allow_reuse_address = True
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nServer stopped.")


if __name__ == "__main__":
    main()
