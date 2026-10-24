import importlib.util
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from mitmproxy import connection, http


SOURCE = Path(__file__).resolve().parents[1] / "cache_addon.py"


class CacheAddonTest(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        (self.root / "cache_addon.py").write_bytes(SOURCE.read_bytes())
        (self.root / "target-sites.txt").write_text(
            "Example | https://example.com/ | example.com\n", encoding="utf-8"
        )

    def load_addon(self, mode):
        spec = importlib.util.spec_from_file_location(
            "cache_addon_under_test", self.root / "cache_addon.py"
        )
        module = importlib.util.module_from_spec(spec)
        with patch.dict(os.environ, {"MITM_CACHE_MODE": mode}):
            spec.loader.exec_module(module)
        return module

    def flow(self, url="https://example.com/article", method="GET"):
        flow = http.HTTPFlow(
            connection.Client(
                peername=("127.0.0.1", 12345), sockname=("127.0.0.1", 8080)
            ),
            connection.Server(address=("example.com", 443)),
        )
        flow.request = http.Request.make(method, url)
        return flow

    def test_allow_miss_remains_available_for_upstream(self):
        addon = self.load_addon("allow")
        flow = self.flow()
        addon.request(flow)
        self.assertIsNone(flow.response)
        self.assertEqual([], list((self.root / "cache").iterdir()))

    def test_saved_binary_response_replays_in_block_mode(self):
        addon = self.load_addon("allow")
        flow = self.flow()
        content = b"\x00\xffsnapshot"
        flow.response = http.Response.make(
            201, content, {"Content-Type": "application/octet-stream", "X-Example": "yes"}
        )
        addon.response(flow)
        addon = self.load_addon("block")
        replay = self.flow()
        addon.request(replay)
        self.assertEqual(201, replay.response.status_code)
        self.assertEqual(content, replay.response.content)
        self.assertEqual("yes", replay.response.headers["X-Example"])

    def test_block_miss_is_not_saved_and_stays_blocked(self):
        addon = self.load_addon("block")
        for _ in range(2):
            flow = self.flow()
            addon.request(flow)
            self.assertEqual(504, flow.response.status_code)
            self.assertEqual("BLOCK", flow.response.headers["X-Cache"])
            addon.response(flow)
        self.assertEqual([], list((self.root / "cache").iterdir()))

    def test_non_target_hosts_pass_through_even_in_block_mode(self):
        addon = self.load_addon("block")
        for host in ("other.example", "example.com.attacker.test", "notexample.com"):
            flow = self.flow(f"https://{host}/")
            addon.request(flow)
            self.assertIsNone(flow.response)
            flow.response = http.Response.make(200, b"not a target")
            addon.response(flow)
        self.assertEqual([], list((self.root / "cache").iterdir()))

    def test_target_subdomains_are_included(self):
        addon = self.load_addon("block")
        flow = self.flow("https://news.example.com/article")
        addon.request(flow)
        self.assertEqual(504, flow.response.status_code)

    def test_method_and_query_distinguish_cached_requests(self):
        addon = self.load_addon("allow")
        flow = self.flow("https://example.com/article?id=1")
        flow.response = http.Response.make(200, b"first article")
        addon.response(flow)
        addon = self.load_addon("block")
        for request in (
            self.flow("https://example.com/article?id=2"),
            self.flow("https://example.com/article?id=1", method="POST"),
        ):
            addon.request(request)
            self.assertEqual(504, request.response.status_code)


if __name__ == "__main__":
    unittest.main()
