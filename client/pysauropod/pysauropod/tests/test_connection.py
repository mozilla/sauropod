
import unittest
import threading
import wsgiref.simple_server

from pysauropod.interfaces import *
from pysauropod.errors import *
from pysauropod.backends.sql import SQLBackend
from pysauropod import server
from pysauropod import connect


_APP = server.main()

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


class SauropodConnectionTests(object):
    """Tests cases to run against a generic ISauropodConnection."""

    def _get_store(self, appid):
        raise NotImplementedError

    def _get_session(self, appid, userid):
        store = self._get_store(appid)
        return store.start_session(userid)

    def test_basic_get_set_delete(self):
        s = self._get_session("APPID", "tester")
        self.assertRaises(KeyError, s.get, "hello")
        item = s.set("hello", "world")
        self.assertEquals(item.key, "hello")
        self.assertEquals(item.value, "world")
        self.assertEquals(s.get("hello"), "world")
        s.delete("hello")
        self.assertRaises(KeyError, s.get, "hello")
        self.assertRaises(KeyError, s.delete, "hello")

    def test_conditional_update(self):
        s = self._get_session("APPID", "tester")
        # For non-existent keys, the required etag is the empty string.
        self.assertRaises(ConflictError,
                          s.set, "hello", "world", if_match="badetag")
        s.set("hello", "world", if_match="")
        # Read it back with an updated etag string.
        item = s.getitem("hello")
        self.assertEquals(item.value, "world")
        self.assertNotEquals(item.etag, "")
        # The etag string is consistent across reads.
        self.assertEquals(s.getitem("hello").etag, item.etag)
        # Updating again requires the given etag.
        self.assertRaises(ConflictError,
                          s.set, "hello", "world", if_match="")
        self.assertRaises(ConflictError,
                          s.set, "hello", "world", if_match=item.etag+"X")
        s.set("hello", "there", if_match=item.etag)
        # Reading it back gives a different etag string.
        item2 = s.getitem("hello")
        self.assertEquals(item2.value, "there")
        self.assertNotEquals(item.etag, item2.etag)
        # Deleting it requires the updated etag string.
        self.assertRaises(ConflictError,
                          s.delete, "hello", if_match="")
        self.assertRaises(ConflictError,
                          s.delete, "hello", if_match=item.etag)
        s.delete("hello", if_match=item2.etag)
        self.assertRaises(KeyError, s.get, "hello")

    def test_listkeys(self):
        s = self._get_session("APPID", "tester")
        s.set("key-one", "one")
        s.set("key-two", "two")
        s.set("key-three", "three")
        self.assertEquals(sorted(s.listkeys()),
                          ["key-one", "key-three", "key-two"])
        self.assertEquals(sorted(s.listkeys(limit=2)),
                          ["key-one", "key-three"])
        self.assertEquals(sorted(s.listkeys(start="key-")),
                          ["key-one", "key-three", "key-two"])
        self.assertEquals(sorted(s.listkeys(start="key-t")),
                          ["key-three", "key-two"])
        self.assertEquals(sorted(s.listkeys(start="key-t", limit=1)),
                          ["key-three"])
        self.assertEquals(sorted(s.listkeys(end="key-per")),
                          ["key-one"])
        self.assertEquals(sorted(s.listkeys(end="apple")), [])
        self.assertEquals(sorted(s.listkeys(start="something-else")), [])



class TestSauropodWebAPI(unittest.TestCase, SauropodConnectionTests):

    def setUp(self):
        self.server = TestingServer()

    def tearDown(self):
        self.server.shutdown()

    def _get_store(self, appid):
        return connect(self.server.base_url, appid, "APPKEY")
