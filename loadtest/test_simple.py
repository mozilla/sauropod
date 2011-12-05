import unittest
import json
import random
from urllib import quote as urlquote
from urllib import unquote as urlunquote
from urlparse import urljoin

from funkload.FunkLoadTestCase import FunkLoadTestCase
from funkload.utils import Data


class SimpleTest(FunkLoadTestCase):

    def setUp(self):
        self.root_url = self.conf_get("main", "url")
        self.num_users = int(self.conf_get("main", "num_users"))
        self.num_keys = int(self.conf_get("main", "num_keys"))

    def start_session(self):
        assertion = "user%d@moz.com" % random.randint(0, self.num_users - 1)
        audience = self.conf_get("main", "audience")
        params = {"audience": audience, "assertion": assertion}
        res = self.post(urljoin(self.root_url, "/session/start"),
                        params=params)
        self.assertEquals(res.code, 200)
        sessionid = res.body
        self.setHeader("Signature", sessionid)
        bucket_url = urljoin(self.root_url,"/app/%s/users/%s/keys/")
        bucket_url %= (urlquote(audience, safe=""),
                       urlquote(assertion, safe=""))
        return sessionid, bucket_url

    def test_write_and_read_keys(self):
        """Test sequentual writing then reading of keys.

        This test does a simple sequential write of a bunch of keys, then
        reads them all back in the same order.
        """
        sessionid, bucket_url = self.start_session()

        # Write out a bunch of keys.
        for i in range(self.num_keys):
            key_url = urljoin(bucket_url, "key%d" % (i,))
            params = {"value": "value%d" % (i,)}
            res = self.put(key_url, params=params)
            self.assertEquals(res.code, 200)

        # Read all the keys back in.
        for i in range(self.num_keys):
            key_url = urljoin(bucket_url, "key%d" % (i,))
            res = self.get(key_url)
            self.assertEquals(res.code, 200)
            self.assertEquals(json.loads(res.body)["value"], "value%d" % (i,))
