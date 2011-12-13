# ***** BEGIN LICENSE BLOCK *****
# Version: MPL 1.1/GPL 2.0/LGPL 2.1
#
# The contents of this file are subject to the Mozilla Public License Version
# 1.1 (the "License"); you may not use this file except in compliance with
# the License. You may obtain a copy of the License at
# http://www.mozilla.org/MPL/
#
# Software distributed under the License is distributed on an "AS IS" basis,
# WITHOUT WARRANTY OF ANY KIND, either express or implied. See the License
# for the specific language governing rights and limitations under the
# License.
#
# The Original Code is Sauropod.
#
# The Initial Developer of the Original Code is the Mozilla Foundation.
# Portions created by the Initial Developer are Copyright (C) 2010
# the Initial Developer. All Rights Reserved.
#
# Contributor(s):
#   Ryan Kelly (rkelly@mozilla.com)
#
# Alternatively, the contents of this file may be used under the terms of
# either the GNU General Public License Version 2 or later (the "GPL"), or
# the GNU Lesser General Public License Version 2.1 or later (the "LGPL"),
# in which case the provisions of the GPL or the LGPL are applicable instead
# of those above. If you wish to allow use of your version of this file only
# under the terms of either the GPL or the LGPL, and not to allow others to
# use your version of this file under the terms of the MPL, indicate your
# decision by deleting the provisions above and replace them with the notice
# and other provisions required by the GPL or the LGPL. If you do not delete
# the provisions above, a recipient may use your version of this file under
# the terms of any one of the MPL, the GPL or the LGPL.
#
# ***** END LICENSE BLOCK *****

import os
import unittest
import threading
import logging
import wsgiref.simple_server

from pyramid import testing
from pyramid.httpexceptions import HTTPException

from pysauropod.errors import ConflictError, AuthenticationError
from pysauropod import connect

import vep


class CaptureLoggingHandler(logging.Handler):
    """Logging handler to capture output in memory."""

    def __init__(self):
        self.messages = []
        logging.Handler.__init__(self)

    def emit(self, record):
        self.messages.append(record)


class SilentWSGIRequestHandler(wsgiref.simple_server.WSGIRequestHandler):
    """WSGIRequestHandler that doesn't print to stderr for each request.

    Because it's really annoying to have each request printed to stdout
    during tests, messing up the carefully formatted output of your
    test runner.
    """
    def log_message(self, format, *args):
        pass


class TestingServer(object):
    """Class to spin up a local WSGI server for testing purposes.

    This class lets you easily run a live webserver in a background thread,
    for testing HTTP-based API.
    """

    def __init__(self, app):
        self.app = app

    def start(self):
        args = ("localhost", 8080, self.app)
        kwds = {"handler_class": SilentWSGIRequestHandler}
        self.server = wsgiref.simple_server.make_server(*args, **kwds)
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
    """Tests cases to run against a generic ISauropodConnection.

    This is a test-suite mixin full of tests to run against a Sauropod
    database connection.  Concrete subclasses must override the _get_store()
    and/or _get_session() methods to instantiate an appropriate connection
    object for testing.
    """

    def _get_store(self, appid):
        raise NotImplementedError

    def _get_session(self, appid, userid):
        store = self._get_store(appid)
        assertion = vep.DummyVerifier.make_assertion(userid, appid)
        credentials = {"audience": appid, "assertion": assertion}
        return store.start_session(userid, credentials)

    def test_basic_get_set_delete(self):
        s = self._get_session("APPID", "test@example.com")
        self.assertRaises(KeyError, s.get, "hello")
        item = s.set("hello", "world")
        self.assertEquals(item.key, "hello")
        self.assertEquals(item.value, "world")
        self.assertEquals(s.get("hello"), "world")
        s.delete("hello")
        self.assertRaises(KeyError, s.get, "hello")
        self.assertRaises(KeyError, s.delete, "hello")

    def test_conditional_update(self):
        s = self._get_session("APPID", "test@example.com")
        # For non-existent keys, the required etag is the empty string.
        self.assertRaises(ConflictError,
                          s.set, "hello", "world", if_match="badetag")
        s.set("hello", "world", if_match="")
        # Read it back and get an updated etag string.
        item = s.getitem("hello")
        self.assertEquals(item.value, "world")
        self.assertNotEquals(item.etag, "")
        # Read it again and the etag has not changed.
        self.assertEquals(s.getitem("hello").etag, item.etag)
        # Updating again requires a correct etag.
        self.assertRaises(ConflictError,
                          s.set, "hello", "world", if_match="")
        self.assertRaises(ConflictError,
                          s.set, "hello", "world", if_match=item.etag + "X")
        s.set("hello", "there", if_match=item.etag)
        # Reading it back now gives a different etag string.
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


class TestSauropodDirectAPI(unittest.TestCase, SauropodConnectionTests):
    """Run the Sauropod testsuite against a local SQL-backed store."""

    def setUp(self):
        pass

    def tearDown(self):
        try:
            os.unlink("/tmp/sauropod.db")
        except EnvironmentError:
            pass

    def _get_store(self, appid):
        kwds = {"create_tables": True,
                "verifier": "vep:DummyVerifier"}
        return connect("sqlite:////tmp/sauropod.db", appid, **kwds)


class TestSauropodWebAPI(unittest.TestCase, SauropodConnectionTests):
    """Run the Sauropod testsuite against the HTTP API.

    This testsuite spins up a wsgiref.simple_server in a background thread,
    hosting a pysauropod.server application.  It then uses the WebAPIConnection
    to run the testsuite against that API.
    """

    def setUp(self):
        self.config = testing.setUp()
        settings = {
           # Serve a local sql-backed sauropod database for testing purposes.
           "sauropod.storage.backend": "pysauropod.backends.sql:SQLBackend",
           "sauropod.storage.sqluri": "sqlite:////tmp/sauropod.db",
           "sauropod.storage.create_tables": True,
           # Stub out the credentials-checking for testing purposes.
           "sauropod.credentials.verifier": "vep:DummyVerifier",
           "sauropod.credentials.backend":
               "pysauropod.server.credentials:BrowserIDCredentials"}
        self.config.add_settings(settings)

        # Load up pysauropod.server.
        self.config.include("pysauropod.server")
        pyramid_app = self.config.make_wsgi_app()

        # Make sure to capture HTTPExceptions and turn them into responses.
        # TODO: convince pyramid test configurator to do this for itself.
        def wrapped_app(environ, start_response):
            try:
                return pyramid_app(environ, start_response)
            except HTTPException, e:
                return e(environ, start_response)

        # Run the server in a background thread.
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

    def test_connection_pooling(self):
        # Capture logging messages from requests module.
        handler = CaptureLoggingHandler()
        logging.getLogger("requests").addHandler(handler)
        logging.getLogger("requests").setLevel(logging.DEBUG)
        try:
            s = self._get_session("APPID", "test@example.com")
            # Make a bunch of requests, so connections get created.
            for _ in xrange(10):
                s.set("hello", "world")
                s.get("hello")
                s.delete("hello")
            # The default pool size is 10.  That should have created
            # precisely 10 new connections.
            count = 0
            for r in handler.messages:
                if "new HTTP connection" in r.getMessage():
                    count += 1
            self.assertEquals(count, 10)
        finally:
            logging.getLogger("requests").removeHandler(handler)
