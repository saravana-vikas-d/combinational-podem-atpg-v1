"""Local server stays on loopback and only serves the viewer directory."""

from __future__ import annotations

import threading
import time
import urllib.error
import urllib.request

from viewer.serve import build_parser, create_server


def test_default_port_is_loopback_only():
    args = build_parser().parse_args([])
    assert args.port == 8765
    server = create_server(0)
    try:
        host, _port = server.server_address[:2]
        assert host == "127.0.0.1"
    finally:
        server.server_close()


def test_serves_viewer_html_and_blocks_parent_paths():
    httpd = create_server(0)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    port = httpd.server_address[1]
    url = f"http://127.0.0.1:{port}/viewer.html"
    try:
        response = None
        last_error = None
        for _ in range(20):
            try:
                response = urllib.request.urlopen(url, timeout=5)
                break
            except urllib.error.URLError as exc:
                last_error = exc
                time.sleep(0.05)
        if response is None:
            raise AssertionError(f"viewer did not start: {last_error}")
        with response:
            body = response.read().decode("utf-8")
            assert response.status == 200
        assert "cytoscape/3.28.1" in body
        try:
            urllib.request.urlopen(
                f"http://127.0.0.1:{port}/../pyproject.toml", timeout=5
            )
        except urllib.error.HTTPError as exc:
            assert exc.code == 404
        else:
            raise AssertionError("parent path was served")
    finally:
        httpd.shutdown()
        httpd.server_close()
