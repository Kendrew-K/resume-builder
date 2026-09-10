"""Localhost bridge for browser-collected job postings.

Claude in Chrome drives the user's own logged-in browser to collect postings
that job_search.sources cannot reach over plain HTTP (LinkedIn and Indeed serve
bot-walled or logged-out markup to urllib). Getting the collected JSON back out
of the page is the awkward part:

  - reading it through the browser tool truncates on large payloads, and
  - LinkedIn/Indeed both set a Content-Security-Policy that blocks the page
    from POSTing to 127.0.0.1 (both fetch and form submission).

So the collecting page stashes its JSON in `window.name` — which survives
cross-origin navigation — and the tab is then pointed at this server. The page
served below is same-origin with this server and carries no CSP, so it can POST
`window.name` back here, where it is written to disk for
`job_search_cli.py ingest`.

Usage: python -m job_search.chrome_receiver chrome_dump.json [port]
Then navigate the collecting tab to http://127.0.0.1:8765/ and it self-posts.

Serves until one POST arrives, then exits, so it is never left listening.
"""
import pathlib
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer

DEFAULT_PORT = 8765

BRIDGE_PAGE = b"""<!doctype html><title>posting...</title><body>
<script>
fetch('/', {method: 'POST', body: window.name})
  .then(r => r.text())
  .then(t => document.body.append('posted ' + window.name.length + ' bytes: ' + t));
</script></body>"""


class _Bridge(BaseHTTPRequestHandler):
    output_path = "chrome_dump.json"
    received = False

    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.send_header("Content-Length", str(len(BRIDGE_PAGE)))
        self.end_headers()
        self.wfile.write(BRIDGE_PAGE)

    def do_POST(self):
        body = self.rfile.read(int(self.headers.get("Content-Length", 0)))
        pathlib.Path(self.output_path).write_bytes(body)
        _Bridge.received = True
        self.send_response(200)
        self.send_header("Content-Length", "2")
        self.end_headers()
        self.wfile.write(b"ok")
        print(f"Wrote {len(body)} bytes to {self.output_path}")

    def log_message(self, *args):
        pass  # suppress per-request stderr noise; the do_POST print is enough


def serve_until_post(output_path, port=DEFAULT_PORT) -> None:
    """Serve the bridge page until one POST arrives, write its body to
    output_path, then stop. Blocks; run it in the background.
    """
    _Bridge.output_path = output_path
    _Bridge.received = False
    server = HTTPServer(("127.0.0.1", port), _Bridge)
    while not _Bridge.received:
        server.handle_request()
    server.server_close()


if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else "chrome_dump.json"
    serve_until_post(path, int(sys.argv[2]) if len(sys.argv) > 2 else DEFAULT_PORT)
