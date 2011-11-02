
import unittest
import threading
import wsgiref.simple_server

from pysauropod.server import main
from pysauropod import Store

_APP = main()

class TestingServer(object):
    """Spin up a local in-memory Sauropod server for testing purposes."""

    def __init__(self):
        # can't seem to call it more than once?
        # app = main()
        app = _APP
        self.base_url = "http://localhost:8080"
        self.server = wsgiref.simple_server.make_server("localhost", 8080, app)
        self.runthread = threading.Thread(target=self.run)
        self.runthread.start()

    def run(self):
        """Run the server in a background thread."""
        self.server.serve_forever()

    def shutdown(self):
        """Explicitly shut down the server."""
        self.server.shutdown()
        self.runthread.join()
        self.server = None


class TestSauropodClient(unittest.TestCase):

    def setUp(self):
        self.server = TestingServer()

    def tearDown(self):
        self.server.shutdown()

    def test_basic_get_set_delete(self):
        store = Store(self.server.base_url, "APP", "APPKEY")
        s = store.start_session("rfk")
        self.assertRaises(KeyError, s.get, "hello")
        s.set("hello", "world")
        self.assertEquals(s.get("hello"), "world")
        s.delete("hello")
        self.assertRaises(KeyError, s.get, "hello")
        self.assertRaises(KeyError, s.delete, "hello")

    def test_listkeys(self):
        store = Store(self.server.base_url, "APP", "APPKEY")
        s = store.start_session("rfk")
        s.set("key-one", "one")
        s.set("key-two", "two")
        s.set("key-three", "three")
        self.assertEquals(sorted(s.listkeys()),
                          ["key-one", "key-three", "key-two"])
        self.assertEquals(sorted(s.listkeys(prefix="key-")),
                          ["key-one", "key-three", "key-two"])
        self.assertEquals(sorted(s.listkeys(prefix="key-t")),
                          ["key-three", "key-two"])
        self.assertEquals(sorted(s.listkeys(prefix="something-else")), [])
