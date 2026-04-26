#!/usr/bin/env python3
"""Tiny static file server for ClipForge.

Usage:
    python3 server.py            # serves on http://localhost:8000
    python3 server.py 9000       # custom port
"""
import http.server
import socketserver
import sys
import os

PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8000

os.chdir(os.path.dirname(os.path.abspath(__file__)))


class Handler(http.server.SimpleHTTPRequestHandler):
    def end_headers(self):
        # MediaRecorder + cross-origin isolation niceties.
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def guess_type(self, path):
        if path.endswith(".js"):
            return "application/javascript"
        return super().guess_type(path)


with socketserver.TCPServer(("", PORT), Handler) as httpd:
    print(f"ClipForge corriendo en http://localhost:{PORT}")
    print("Ctrl+C para salir.")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nAdiós.")
