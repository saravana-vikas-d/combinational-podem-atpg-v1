"""Serve the viewer on localhost only.

The server root is the ``viewer/`` directory. It does not serve the rest of
the repository and it binds to 127.0.0.1.
"""

from __future__ import annotations

import argparse
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import quote


VIEWER_ROOT = Path(__file__).resolve().parent


class _ViewerHandler(SimpleHTTPRequestHandler):
    def end_headers(self) -> None:
        self.send_header("Cache-Control", "no-store")
        super().end_headers()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Serve viewer/ on 127.0.0.1 for the circuit visualizer"
    )
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument(
        "--snapshot",
        default="output/circuit.json",
        help="Snapshot path relative to viewer/, used only in the printed URL",
    )
    return parser


def create_server(port: int) -> ThreadingHTTPServer:
    """Bind only to loopback and serve files inside ``viewer/``."""
    handler = partial(_ViewerHandler, directory=str(VIEWER_ROOT))
    return ThreadingHTTPServer(("127.0.0.1", port), handler)


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.port < 1 or args.port > 65535:
        parser.error("port must be between 1 and 65535")

    server = create_server(args.port)
    snapshot = quote(args.snapshot, safe="/")
    url = f"http://127.0.0.1:{args.port}/viewer.html?snapshot={snapshot}"
    print(f"serving {VIEWER_ROOT}")
    print(url)
    print("stop with Ctrl+C")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print()
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
