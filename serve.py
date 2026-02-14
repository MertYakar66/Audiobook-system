#!/usr/bin/env python3
"""
Simple HTTP server with Range request support.
Required for audio seeking in the web reader.

Usage: python serve.py [port]
Default port: 8000
"""

import os
import sys
import mimetypes
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path


class RangeHTTPRequestHandler(SimpleHTTPRequestHandler):
    """HTTP handler that supports Range requests for audio/video seeking."""

    def send_head(self):
        path = self.translate_path(self.path)

        if os.path.isdir(path):
            return super().send_head()

        if not os.path.isfile(path):
            self.send_error(404, "File not found")
            return None

        # Get file info
        file_size = os.path.getsize(path)
        content_type, _ = mimetypes.guess_type(path)
        if content_type is None:
            content_type = "application/octet-stream"

        # Check for Range header
        range_header = self.headers.get("Range")

        if range_header:
            try:
                # Parse range (e.g., "bytes=1000-2000" or "bytes=1000-")
                range_spec = range_header.replace("bytes=", "")
                parts = range_spec.split("-")
                start = int(parts[0]) if parts[0] else 0
                end = int(parts[1]) if parts[1] else file_size - 1
                end = min(end, file_size - 1)
                length = end - start + 1

                self.send_response(206)
                self.send_header("Content-Type", content_type)
                self.send_header("Content-Length", str(length))
                self.send_header("Content-Range", f"bytes {start}-{end}/{file_size}")
                self.send_header("Accept-Ranges", "bytes")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()

                f = open(path, "rb")
                f.seek(start)
                return _RangeFile(f, length)

            except (ValueError, IndexError):
                self.send_error(416, "Invalid range")
                return None
        else:
            # Normal request - still advertise Range support
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(file_size))
            self.send_header("Accept-Ranges", "bytes")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            return open(path, "rb")


class _RangeFile:
    """Wrapper to read only a portion of a file."""

    def __init__(self, f, length):
        self.f = f
        self.remaining = length

    def read(self, size=-1):
        if self.remaining <= 0:
            return b""
        if size < 0 or size > self.remaining:
            size = self.remaining
        data = self.f.read(size)
        self.remaining -= len(data)
        return data

    def close(self):
        self.f.close()


def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
    server = HTTPServer(("", port), RangeHTTPRequestHandler)
    print(f"Serving at http://localhost:{port}")
    print(f"Open http://localhost:{port}/web/library.html")
    print("Press Ctrl+C to stop")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServer stopped.")
        server.server_close()


if __name__ == "__main__":
    main()
