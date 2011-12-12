import unittest
import json
import random
from urllib import quote as urlquote
from urllib import unquote as urlunquote
from urlparse import urljoin

import vep

from funkload.FunkLoadTestCase import FunkLoadTestCase
from funkload.utils import Data


class SauropodTests(FunkLoadTestCase):
    """FunkLoad-based load tests for Sauropod HTTP server."""

    def setUp(self):
        self.root_url = self.conf_get("main", "url")
        self.audience = self.conf_get("main", "audience")
        self.num_users = int(self.conf_get("main", "num_users"))
        self.userid = None

    def tearDown(self):
        self.userid = None

    def start_session(self, userid=None):
        if userid is None:
            userid = "user%d@moz.com" % random.randint(0, self.num_users - 1)
        assertion = vep.DummyVerifier.make_assertion(userid, self.audience)
        params = {"audience": self.audience, "assertion": assertion}
        res = self.post(urljoin(self.root_url, "/session/start"),
                        params=params)
        self.assertEquals(res.code, 200)
        self.sessionid = res.body
        self.userid = userid
        self.setHeader("Signature", self.sessionid)

    def get_keypath(self, key, userid=None, appid=None):
        if userid is None:
            userid = self.userid
        if appid is None:
            appid = self.audience
        keypath = urljoin(self.root_url,"/app/%s/users/%s/keys/%s")
        keypath %= (urlquote(appid, safe=""),
                    urlquote(userid, safe=""),
                    urlquote(key, safe=""))
        return keypath
        
    def get_key(self, key, userid=None, appid=None):
        keypath = self.get_keypath(key, userid, appid)
        res = self.get(keypath)
        self.assertEquals(res.code, 200)
        return json.loads(res.body)["value"]

    def set_key(self, key, value, userid=None, appid=None):
        keypath = self.get_keypath(key, userid, appid)
        res = self.put(keypath, params={"value": value})
        self.assertTrue(200 <= res.code < 300)

    def del_key(self, key, value, userid=None, appid=None):
        keypath = self.get_keypath(key, userid, appid)
        params = {"value": "value%d" % (i,)}
        res = self.delete(keypath)
        self.assertTrue(200 <= res.code < 300)

    def test_write_read_seq(self):
        """Test sequentual writing then reading of keys.

        This test does a simple sequential write of a bunch of keys, then
        reads them all back in the same order.
        """
        num_keys = 20
        self.start_session()
        # Write out a bunch of keys.
        for i in range(num_keys):
            self.set_key("key%d" % (i,), "value%d" % (i,))
        # Read all the keys back in.
        for i in range(num_keys):
            value = self.get_key("key%d" % (i,))
            self.assertEquals(value, "value%d" % (i,))

    def test_contention_for_single_key(self):
        """Test contention for a single key.

        This test does a bunch of reads and writes of a single key, to
        see how we go under hotly contested scenarios.
        """
        self.start_session("user1@moz.com")
        for i in range(20):
            self.set_key("hot-key", "we all want this key baby")
            value = self.get_key("hot-key")
            self.assertEquals(value, "we all want this key baby")


if __name__ == "__main__":
    import os
    import sys
    import subprocess
    # Sanity-check the setup by running a single instance of the tests.
    print "SANITY-CHECKING YOUR SETUP"
    subprocess.check_call(["fl-run-test", __file__])
    # Now we can run the full benchmark suite.
    for methnm in dir(SauropodTests):
        if not methnm.startswith("test_"):
            continue
        print "RUNNING THE BENCHMARK", methnm
        subprocess.check_call(["fl-run-bench", __file__,
                               "SauropodTests." + methnm])
        print "GENERATING THE REPORT"
        subprocess.check_call(["fl-build-report", "--html",
                               "--output-directory=html",
                               "sauropod-bench.xml"])
