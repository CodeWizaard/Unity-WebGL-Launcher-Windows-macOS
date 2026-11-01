#!/usr/bin/env python3
"""Read-only Unity WebGL preview server. Python 3.9+, standard library only."""
from __future__ import annotations

import ipaddress
import mimetypes
from pathlib import Path
import re
import shutil
import socket
from socketserver import TCPServer
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import unquote, urlsplit


MIME_TYPES = {
    ".html": "text/html; charset=utf-8", ".htm": "text/html; charset=utf-8",
    ".js": "application/javascript", ".mjs": "application/javascript",
    ".wasm": "application/wasm", ".data": "application/octet-stream",
    ".bundle": "application/octet-stream", ".bin": "application/octet-stream",
    ".unityweb": "application/octet-stream", ".json": "application/json",
    ".css": "text/css; charset=utf-8", ".svg": "image/svg+xml",
}


def response_type(path: Path) -> tuple[str, str | None]:
    name = path.name.lower()
    encoding = None
    if name.endswith(".gz"):
        encoding, name = "gzip", name[:-3]
    elif name.endswith(".br"):
        encoding, name = "br", name[:-3]
    suffix = Path(name).suffix
    mime = MIME_TYPES.get(suffix) or mimetypes.guess_type(name)[0] or "application/octet-stream"
    # Unity's server examples use this MIME for Safari's compressed-data workaround.
    if encoding == "gzip" and suffix == ".data":
        mime = "application/gzip"
    return mime, encoding


class WebGLServer(ThreadingHTTPServer):
    daemon_threads = True
    block_on_close = False
    allow_reuse_address = sys.platform != "win32"
    request_queue_size = 32

    def server_bind(self):
        # HTTPServer normally performs reverse DNS here. The preview needs only
        # the numeric address; offline/VPN/macOS DNS must not delay startup.
        TCPServer.server_bind(self)
        self.server_name, self.server_port = self.server_address[:2]

    def __init__(self, root: Path, entry: str, host: str, port: int):
        self.root = root.resolve(strict=True)
        self.entry = entry
        self._slots = threading.BoundedSemaphore(16)
        super().__init__((host, port), WebGLHandler)

    def process_request(self, request, client_address):
        if not self._slots.acquire(timeout=1):
            try:
                request.sendall(b"HTTP/1.0 503 Service Unavailable\r\nContent-Length: 0\r\nConnection: close\r\n\r\n")
            finally:
                self.shutdown_request(request)
            return
        try:
            super().process_request(request, client_address)
        except BaseException:
            self._slots.release()
            raise

    def process_request_thread(self, request, client_address):
        try:
            super().process_request_thread(request, client_address)
        finally:
            self._slots.release()


class WebGLHandler(BaseHTTPRequestHandler):
    server_version = "UnityWebGLPreview/1.0"
    sys_version = ""
    protocol_version = "HTTP/1.0"

    def log_message(self, format, *args):
        # Windowed executables have no stderr.
        pass

    def setup(self):
        self.request.settimeout(30)
        super().setup()

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        self.send_header("Cross-Origin-Opener-Policy", "same-origin")
        self.send_header("Cross-Origin-Embedder-Policy", "require-corp")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Connection", "close")
        super().end_headers()

    def _host_allowed(self) -> bool:
        values = self.headers.get_all("Host", [])
        if len(values) != 1:
            return False
        port = self.server.server_address[1]
        local_ip = self.connection.getsockname()[0]
        allowed = {f"127.0.0.1:{port}", f"localhost:{port}", f"{local_ip}:{port}"}
        if port == 80:
            allowed.update({"127.0.0.1", "localhost", local_ip})
        return values[0].lower() in allowed

    def _resolve_file(self) -> Path:
        raw = self.path
        if not raw.startswith("/") or raw.startswith("//"):
            raise ValueError("Only origin-relative paths are accepted")
        encoded = urlsplit(raw).path
        if re.search(r"%(?![0-9a-fA-F]{2})", encoded):
            raise ValueError("Invalid URL escape")
        decoded = unquote(encoded, encoding="utf-8", errors="strict")
        if decoded == "/":
            decoded = "/" + self.server.entry
        parts = decoded[1:].split("/")
        current = self.server.root
        for part in parts:
            if not part or part.startswith(".") or part.endswith((".", " ")) or any(c in part for c in '\\<>:"|?*\x00'):
                raise PermissionError("Invalid path component")
            if any(ord(c) < 32 for c in part):
                raise PermissionError("Control characters are not allowed")
            current = current / part
            if current.is_symlink():
                raise PermissionError("Symbolic links are not served")
        resolved = current.resolve(strict=True)
        try:
            resolved.relative_to(self.server.root)
        except ValueError:
            raise PermissionError("Path is outside the build folder") from None
        if not resolved.is_file():
            raise FileNotFoundError("Directory listings are disabled")
        return resolved

    def _serve(self, head: bool = False):
        if not self._host_allowed():
            self.send_error(403, "Forbidden Host")
            return
        try:
            path = self._resolve_file()
            with path.open("rb") as source:
                size = path.stat().st_size
                mime, encoding = response_type(path)
                self.send_response(200)
                self.send_header("Content-Type", mime)
                self.send_header("Content-Length", str(size))
                if encoding:
                    self.send_header("Content-Encoding", encoding)
                self.end_headers()
                if not head:
                    shutil.copyfileobj(source, self.wfile, length=64 * 1024)
        except (UnicodeError, ValueError):
            self.send_error(400, "Bad Request")
        except PermissionError:
            self.send_error(403, "Forbidden")
        except (FileNotFoundError, NotADirectoryError, IsADirectoryError):
            self.send_error(404, "Not Found")
        except (BrokenPipeError, ConnectionResetError, TimeoutError):
            pass

    def do_GET(self):
        self._serve()

    def do_HEAD(self):
        self._serve(head=True)

    def _unsupported(self):
        self.send_response(405)
        self.send_header("Allow", "GET, HEAD")
        self.send_header("Content-Length", "0")
        self.end_headers()

    do_POST = do_PUT = do_DELETE = do_PATCH = do_OPTIONS = _unsupported


def lan_addresses() -> list[str]:
    found = []
    # Query routing without sending a packet; prefer the active interface.
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
            probe.connect(("192.0.2.1", 9))
            found.append(probe.getsockname()[0])
    except OSError:
        pass
    if sys.platform == "darwin":
        try:
            result = subprocess.run(["/sbin/ifconfig"], capture_output=True, text=True, timeout=3)
            found.extend(re.findall(r"\binet (\d+\.\d+\.\d+\.\d+)\b", result.stdout))
        except (OSError, subprocess.TimeoutExpired):
            pass
    if sys.platform != "darwin" or not found:
        try:
            found.extend(socket.gethostbyname_ex(socket.gethostname())[2])
        except OSError:
            pass
    addresses = []
    for value in found:
        try:
            ip = ipaddress.IPv4Address(value)
        except ipaddress.AddressValueError:
            continue
        if not ip.is_loopback and not ip.is_link_local and not ip.is_unspecified and value not in addresses:
            addresses.append(value)
    return addresses


class Preview:
    """Own the listening socket and its lifecycle independently of the UI."""

    def __init__(self):
        self.server = None
        self.thread = None
        self.local_url = ""
        self.phone_urls = []

    @property
    def running(self):
        return self.server is not None

    def start(self, selected: str, lan: bool = False):
        if self.running:
            raise ValueError("Сначала остановите текущий билд.")
        if not selected.strip():
            raise ValueError("Выберите index.html или папку WebGL-билда.")
        entry = Path(selected.strip()).expanduser()
        if entry.is_dir():
            entry = entry / "index.html"
        try:
            entry = entry.resolve(strict=True)
        except OSError as error:
            raise ValueError("Файл не найден. Выберите index.html или папку, в которой он находится.") from error
        if not entry.is_file() or entry.suffix.lower() not in (".html", ".htm"):
            raise ValueError("Выберите HTML-файл. ZIP-архив сначала нужно распаковать.")
        addresses = lan_addresses() if lan else []
        server = WebGLServer(entry.parent, entry.name, "0.0.0.0" if lan else "127.0.0.1", 0)
        thread = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.1}, daemon=True)
        try:
            thread.start()
        except Exception:
            server.server_close()
            raise
        self.server, self.thread = server, thread
        port = server.server_address[1]
        self.local_url = f"http://127.0.0.1:{port}/"
        self.phone_urls = [f"http://{address}:{port}/" for address in addresses]

    def stop(self):
        if self.server is not None:
            self.server.shutdown()
            self.server.server_close()
            self.thread.join(timeout=2)
            self.server = self.thread = None
            self.local_url = ""
            self.phone_urls = []
