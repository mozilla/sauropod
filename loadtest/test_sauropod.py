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
        num_keys = int(self.conf_get("test_write_read_seq", "num_keys"))
        self.start_session()
        # Write out a bunch of keys.
        for i in range(num_keys):
            self.set_key("key%d" % (i,), "value%d" % (i,))
        # Read all the keys back in.
        for i in range(num_keys):
            value = self.get_key("key%d" % (i,))
            self.assertEquals(value, "value%d" % (i,))
