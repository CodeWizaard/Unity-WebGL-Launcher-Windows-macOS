import gzip
import http.client
from pathlib import Path
import socket
import tempfile
import unittest
from unittest.mock import patch
from urllib.parse import urlsplit

from unity_webgl_launcher.server import Preview


class ServerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        (self.root / "index.html").write_text("<html>Preview</html>", encoding="utf-8")
        (self.root / "Build").mkdir()
        self.preview = Preview()
        self.preview.start(str(self.root))
        self.port = urlsplit(self.preview.local_url).port

    def tearDown(self):
        self.preview.stop()
        self.temp.cleanup()

    def request(self, path="/", method="GET", headers=None):
        connection = http.client.HTTPConnection("127.0.0.1", self.port, timeout=3)
        connection.request(method, path, headers=headers or {})
        response = connection.getresponse()
        result = response.status, dict(response.getheaders()), response.read()
        connection.close()
        return result

    def test_index_and_isolation(self):
        status, headers, body = self.request()
        self.assertEqual(status, 200)
        self.assertIn(b"Preview", body)
        self.assertEqual(headers["Cross-Origin-Opener-Policy"], "same-origin")
        self.assertEqual(headers["Cross-Origin-Embedder-Policy"], "require-corp")
        self.assertEqual(headers["Cache-Control"], "no-store")
        self.assertEqual(self.preview.server.server_address[0], "127.0.0.1")

    def test_compression_and_mime(self):
        for filename, mime, encoding in [
            ("game.wasm", "application/wasm", None),
            ("game.wasm.gz", "application/wasm", "gzip"),
            ("game.framework.js.br", "application/javascript", "br"),
            ("game.data.gz", "application/gzip", "gzip"),
            ("game.wasm.unityweb", "application/octet-stream", None),
        ]:
            with self.subTest(filename=filename):
                payload = gzip.compress(b"test") if encoding == "gzip" else b"test"
                (self.root / "Build" / filename).write_bytes(payload)
                status, headers, body = self.request("/Build/" + filename)
                self.assertEqual(status, 200)
                self.assertEqual(body, payload)
                self.assertEqual(headers["Content-Type"], mime)
                self.assertEqual(headers.get("Content-Encoding"), encoding)
                self.assertEqual(int(headers["Content-Length"]), len(payload))

    def test_head(self):
        status, headers, body = self.request(method="HEAD")
        self.assertEqual(status, 200)
        self.assertGreater(int(headers["Content-Length"]), 0)
        self.assertEqual(body, b"")

    def test_invalid_requests_and_traversal(self):
        for path, expected in [("/../secret", 403), ("/%2e%2e/secret", 403), ("/%5csecret", 403), ("/bad%00", 403), ("/bad%xx", 400), ("/.git/config", 403), ("/Build", 404), ("/missing", 404)]:
            with self.subTest(path=path):
                self.assertEqual(self.request(path)[0], expected)
        self.assertEqual(self.request(headers={"Host": "evil.example"})[0], 403)
        self.assertEqual(self.request(method="POST")[0], 405)

    def test_unicode_and_query(self):
        (self.root / "Привет мир.js").write_bytes(b"hello")
        self.assertEqual(self.request("/%D0%9F%D1%80%D0%B8%D0%B2%D0%B5%D1%82%20%D0%BC%D0%B8%D1%80.js?v=1")[2], b"hello")

    def test_stop_releases_port_and_restart(self):
        self.preview.stop()
        with socket.socket() as probe:
            probe.settimeout(1)
            self.assertNotEqual(probe.connect_ex(("127.0.0.1", self.port)), 0)
        self.preview.start(str(self.root / "index.html"))
        self.assertTrue(self.preview.running)
        self.preview.stop()
        self.preview.stop()

    def test_lan(self):
        self.preview.stop()
        with patch("unity_webgl_launcher.server.lan_addresses", return_value=["192.168.1.2"]), patch("socket.getfqdn", side_effect=AssertionError("Server startup must not wait for DNS")):
            self.preview.start(str(self.root), lan=True)
        self.assertEqual(self.preview.server.server_address[0], "0.0.0.0")
        self.assertTrue(self.preview.phone_urls[0].startswith("http://192.168.1.2:"))

    def test_invalid_selection(self):
        self.preview.stop()
        for selected in ["", str(self.root / "missing.html"), str(self.root / "game.zip")]:
            with self.subTest(selected=selected), self.assertRaises(ValueError):
                self.preview.start(selected)

    def test_symlink_is_not_served(self):
        try:
            (self.root / "link.html").symlink_to(self.root / "index.html")
        except OSError:
            self.skipTest("Symlink creation requires permission on this host")
        self.assertEqual(self.request("/link.html")[0], 403)


if __name__ == "__main__":
    unittest.main()
