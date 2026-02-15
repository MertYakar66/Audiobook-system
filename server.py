#!/usr/bin/env python3
"""
Simple HTTP server with Range request support.
Required for audio seeking in the browser.

Usage: python server.py [port]
Default port: 8000
"""

import os
import sys
import mimetypes
from http.server import HTTPServer, SimpleHTTPRequestHandler
from socketserver import ThreadingMixIn

class RangeHTTPRequestHandler(SimpleHTTPRequestHandler):
    """HTTP handler that supports Range requests for audio seeking."""

    def do_GET(self):
        range_header = self.headers.get('Range')
        if not range_header:
            return super().do_GET()

        path = self.translate_path(self.path)
        if not os.path.isfile(path):
            self.send_error(404, "File not found")
            return

        file_size = os.path.getsize(path)
        # Parse Range header: "bytes=start-end"
        try:
            range_spec = range_header.replace('bytes=', '')
            parts = range_spec.split('-')
            start = int(parts[0]) if parts[0] else 0
            end = int(parts[1]) if parts[1] else file_size - 1
        except (ValueError, IndexError):
            self.send_error(416, "Invalid range")
            return

        if start >= file_size or end >= file_size:
            end = file_size - 1

        content_length = end - start + 1
        content_type = mimetypes.guess_type(path)[0] or 'application/octet-stream'

        self.send_response(206)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(content_length))
        self.send_header('Content-Range', f'bytes {start}-{end}/{file_size}')
        self.send_header('Accept-Ranges', 'bytes')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()

        with open(path, 'rb') as f:
            f.seek(start)
            self.wfile.write(f.read(content_length))

    def do_HEAD(self):
        path = self.translate_path(self.path)
        if os.path.isfile(path):
            file_size = os.path.getsize(path)
            content_type = mimetypes.guess_type(path)[0] or 'application/octet-stream'
            self.send_response(200)
            self.send_header('Content-Type', content_type)
            self.send_header('Content-Length', str(file_size))
            self.send_header('Accept-Ranges', 'bytes')
            self.end_headers()
        else:
            self.send_error(404)

    def end_headers(self):
        self.send_header('Accept-Ranges', 'bytes')
        super().end_headers()


class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    """Handle requests in separate threads so audio downloads don't block page loads."""
    daemon_threads = True


if __name__ == '__main__':
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
    server = ThreadedHTTPServer(('0.0.0.0', port), RangeHTTPRequestHandler)
    print(f'Serving on http://localhost:{port} (multi-threaded, with Range request support)')
    print('Press Ctrl+C to stop')
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print('\nStopped.')
