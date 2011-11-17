
import os
import unittest
import threading
import wsgiref.simple_server

from pyramid import testing
from pyramid.httpexceptions import HTTPException

from pysauropod.errors import ConflictError
from pysauropod import server
from pysauropod import connect



class TestingServer(object):
    """Spin up a local WSGI server for testing purposes."""

    def __init__(self, app):
        self.app = app

    def start(self):
        server_args = ("localhost", 8080, self.app)
        self.server = wsgiref.simple_server.make_server(*server_args)
        self.runthread = threading.Thread(target=self.run)
        self.runthread.start()
        self.base_url = "http://localhost:8080"

    def run(self):
        """Run the server in a background thread."""
        self.server.serve_forever()

    def shutdown(self):
        """Explicitly shut down the server."""
        self.server.shutdown()
        self.runthread.join()
        del self.server
        del self.runthread
        del self.base_url


class SauropodConnectionTests(object):
    """Tests cases to run against a generic ISauropodConnection."""

    def _get_store(self, appid):
        raise NotImplementedError

    def _get_session(self, appid, userid):
        store = self._get_store(appid)
        credentials = {"audience": appid, "assertion": userid}
        return store.start_session(userid, credentials)

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
                          s.set, "hello", "world", if_match=item.etag + "X")
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



class TestSauropodWebAPI(unittest.TestCase, SauropodConnectionTests):

    def setUp(self):
        self.config = testing.setUp()
        settings = {
           "sauropod.credentials.backend":
               "pysauropod.server.credentials:DummyCredentials"}
        self.config.add_settings(settings)
        self.config.include("pysauropod.server")
        pyramid_app = self.config.make_wsgi_app()
        def wrapped_app(environ, start_response):
            try:
                return pyramid_app(environ, start_response)
            except HTTPException, e:
                return e(environ, start_response)
        self.app = wrapped_app
        self.server = TestingServer(self.app)
        self.server.start()

    def tearDown(self):
        self.server.shutdown()
        try:
            os.unlink("/tmp/sauropod.db")
        except EnvironmentError:
            pass

    def _get_store(self, appid):
        return connect(self.server.base_url, appid)



class TestSauropodDirectAPI(unittest.TestCase, SauropodConnectionTests):

    def setUp(self):
        pass

    def tearDown(self):
        try:
            os.unlink("/tmp/sauropod.db")
        except EnvironmentError:
            pass

    def _get_store(self, appid):
        return connect("sqlite:////tmp/sauropod.db", appid, create_tables=True)
