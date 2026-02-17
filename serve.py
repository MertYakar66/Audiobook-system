#!/usr/bin/env python3
"""
HTTP server with Range request and gzip compression support.
Required for audio seeking and fast page loads in the web reader.

Usage: python serve.py [port]
Default port: 8000
"""

import gzip
import io
import os
import sys
import mimetypes
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path

# File types that benefit from gzip compression
COMPRESSIBLE_TYPES = {
    "application/json",
    "text/html",
    "text/css",
    "text/javascript",
    "application/javascript",
    "text/plain",
    "application/xml",
    "text/xml",
    "image/svg+xml",
}

# Cache durations (seconds) by content type
CACHE_RULES = {
    "audio/mpeg": 86400 * 7,     # Audio: 7 days
    "audio/wav": 86400 * 7,
    "application/json": 3600,     # JSON: 1 hour
    "text/html": 0,               # HTML: no cache
    "text/css": 3600,             # CSS: 1 hour
    "text/javascript": 3600,      # JS: 1 hour
    "application/javascript": 3600,
    "image/jpeg": 86400 * 7,     # Images: 7 days
    "image/png": 86400 * 7,
    "image/webp": 86400 * 7,
}


class FastHTTPRequestHandler(SimpleHTTPRequestHandler):
    """HTTP handler with Range requests, gzip compression, and caching."""

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

        # Cache duration
        cache_seconds = CACHE_RULES.get(content_type, 3600)

        # Check for Range header (audio seeking)
        range_header = self.headers.get("Range")

        if range_header:
            return self._handle_range_request(path, file_size, content_type, range_header, cache_seconds)
        else:
            return self._handle_normal_request(path, file_size, content_type, cache_seconds)

    def _handle_range_request(self, path, file_size, content_type, range_header, cache_seconds):
        """Handle Range requests for audio seeking."""
        try:
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
            if cache_seconds > 0:
                self.send_header("Cache-Control", f"public, max-age={cache_seconds}")
            self.end_headers()

            f = open(path, "rb")
            f.seek(start)
            return _RangeFile(f, length)

        except (ValueError, IndexError):
            self.send_error(416, "Invalid range")
            return None

    def _handle_normal_request(self, path, file_size, content_type, cache_seconds):
        """Handle normal requests with optional gzip compression."""
        # Check if client accepts gzip and file type is compressible
        accept_encoding = self.headers.get("Accept-Encoding", "")
        use_gzip = (
            "gzip" in accept_encoding
            and content_type in COMPRESSIBLE_TYPES
            and file_size > 1024  # Only compress files > 1KB
        )

        if use_gzip:
            # Read and compress the file
            with open(path, "rb") as f:
                raw_data = f.read()

            buf = io.BytesIO()
            with gzip.GzipFile(fileobj=buf, mode="wb", compresslevel=6) as gz:
                gz.write(raw_data)
            compressed = buf.getvalue()

            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(compressed)))
            self.send_header("Content-Encoding", "gzip")
            self.send_header("Accept-Ranges", "bytes")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Vary", "Accept-Encoding")
            if cache_seconds > 0:
                self.send_header("Cache-Control", f"public, max-age={cache_seconds}")
            else:
                self.send_header("Cache-Control", "no-cache")
            self.end_headers()

            return io.BytesIO(compressed)
        else:
            # No compression - serve raw
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(file_size))
            self.send_header("Accept-Ranges", "bytes")
            self.send_header("Access-Control-Allow-Origin", "*")
            if cache_seconds > 0:
                self.send_header("Cache-Control", f"public, max-age={cache_seconds}")
            else:
                self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            return open(path, "rb")

    def log_message(self, format, *args):
        """Quieter logging - only show non-200 or slow requests."""
        # Still log everything but more concisely
        msg = format % args
        if "200" not in msg and "206" not in msg:
            sys.stderr.write(f"[{self.log_date_time_string()}] {msg}\n")


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
    server = HTTPServer(("", port), FastHTTPRequestHandler)
    print(f"Serving at http://localhost:{port}")
    print(f"Open http://localhost:{port}/web/library.html")
    print(f"Gzip compression: ENABLED for JSON/HTML/CSS/JS")
    print("Press Ctrl+C to stop")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServer stopped.")
        server.server_close()


if __name__ == "__main__":
    main()
