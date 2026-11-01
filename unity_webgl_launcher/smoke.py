"""CI-only entry point to exercise the packaged UI and server."""
import gzip
from contextlib import closing
import http.client
import json
from pathlib import Path
import tempfile
import tkinter as tk
import traceback
from unittest.mock import patch
from urllib.parse import urlsplit

from .app import Launcher


def run(report_path: str) -> int:
    window = None
    app = None
    result = {"ok": False}
    try:
        window = tk.Tk()
        window.withdraw()
        app = Launcher(window)
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "index.html").write_text("<html>Launcher smoke test</html>", encoding="utf-8")
            (root / "test.wasm.gz").write_bytes(gzip.compress(b"\x00asm\x01\x00\x00\x00"))
            app.path.set(folder)
            with patch("unity_webgl_launcher.app.webbrowser.open", return_value=True):
                app.toggle()
                window.update()
                assert app.preview.running
                port = urlsplit(app.preview.local_url).port
                with closing(http.client.HTTPConnection("127.0.0.1", port, timeout=5)) as connection:
                    connection.request("GET", "/test.wasm.gz")
                    response = connection.getresponse()
                    assert response.status == 200
                    assert response.getheader("Content-Encoding") == "gzip"
                    assert response.getheader("Content-Type") == "application/wasm"
                    assert gzip.decompress(response.read()) == b"\x00asm\x01\x00\x00\x00"
                app.copy()
                assert window.clipboard_get() == app.preview.local_url
                app.toggle()
                assert not app.preview.running
                app.mode.set("lan")
                with patch("unity_webgl_launcher.server.lan_addresses", return_value=["192.168.1.2"]):
                    app.toggle()
                assert app.address.get().startswith("http://192.168.1.2:")
                assert app.preview.server.server_address[0] == "0.0.0.0"
                app.toggle()
                assert not app.preview.running
            result = {"ok": True, "checks": ["Tk window", "start", "gzip WASM", "copy address", "stop", "LAN restart"]}
    except Exception:
        result["error"] = traceback.format_exc()
    finally:
        if app:
            app.preview.stop()
        if window:
            window.destroy()
        Path(report_path).write_text(json.dumps(result, indent=2), encoding="utf-8")
    return 0 if result["ok"] else 1
