from __future__ import annotations

import hashlib
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from hantts.core.catalog import Asset
from hantts.core.download import CancelToken, download_asset
from hantts.core.errors import DownloadError


def test_download_and_hash(tmp_path: Path) -> None:
    payload = b"hantts-model-bytes"
    digest = hashlib.sha256(payload).hexdigest()
    server, url = _serve(payload)
    try:
        asset = Asset("model.bin", digest, len(payload), (url,))
        dest = tmp_path / "model.bin"
        seen: list[int] = []
        download_asset(asset, dest, on_progress=lambda done, total, speed, eta: seen.append(done))
        assert dest.read_bytes() == payload
        assert seen[-1] == len(payload)
    finally:
        server.shutdown()


def test_rejects_bad_hash(tmp_path: Path) -> None:
    server, url = _serve(b"nope")
    try:
        asset = Asset("a.bin", "0" * 64, 4, (url,))
        try:
            download_asset(asset, tmp_path / "a.bin", retries=1)
        except DownloadError:
            return
        raise AssertionError("hash mismatch should fail")
    finally:
        server.shutdown()


def test_resume(tmp_path: Path) -> None:
    payload = b"abcdefghij" * 100
    digest = hashlib.sha256(payload).hexdigest()
    part = tmp_path / "a.bin.part"
    part.write_bytes(payload[:40])
    server, url = _serve(payload, ranged=True)
    try:
        asset = Asset("a.bin", digest, len(payload), (url,))
        dest = tmp_path / "a.bin"
        download_asset(asset, dest)
        assert dest.read_bytes() == payload
    finally:
        server.shutdown()


def test_cancel(tmp_path: Path) -> None:
    from hantts.core.errors import CancelledError

    token = CancelToken()
    token.cancel()
    asset = Asset("a.bin", "ab" * 32, 1, ("http://127.0.0.1/missing",))
    try:
        download_asset(asset, tmp_path / "a.bin", cancel=token, retries=1)
    except CancelledError:
        return
    raise AssertionError("cancel should raise")


def _serve(payload: bytes, ranged: bool = False) -> tuple[ThreadingHTTPServer, str]:
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802
            start = 0
            end = len(payload) - 1
            header = self.headers.get("Range")
            if ranged and header and header.startswith("bytes="):
                start = int(header.split("=")[1].split("-")[0] or 0)
                body = payload[start:]
                self.send_response(206)
                self.send_header("Content-Range", f"bytes {start}-{end}/{len(payload)}")
            else:
                body = payload
                self.send_response(200)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, fmt: str, *args: object) -> None:
            return

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, port = server.server_address[:2]
    return server, f"http://{host}:{port}/file"
