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
"""

Sauropod:  a massive impervious data-store
==========================================

Sauropod is a key-value store.  It is designed for secure, scalable storage of
multi-tenanted data.  It supports millions of users and thousands of different
applications all accessing a single instances of the store, without trampling
on each others data or each others privacy.

"""

import os
import cgi
import time
import hmac
from hashlib import sha1
from base64 import b64encode
from urllib2 import HTTPError
from urlparse import urlparse, urljoin
from urllib import quote as urlquote
from urllib import unquote as urlunquote

import requests

from zope.interface import implements

from pysauropod.errors import *
from pysauropod.interfaces import ISauropodConnection, ISauropodSession, Item
from pysauropod.backends.sql import SQLBackend


def connect(url, *args, **kwds):
    """Connect to a Saruopod data store at the given URL.

    This if a helper function to connect to various Sauropod implementations.
    Depending on the URL scheme it will load an appropriate backend and 
    return an object implementing ISauropodConnection.
    """
    scheme = urlparse(url).scheme.lower()
    # HTTP urls use the web connector.
    if scheme in ("http", "https"):
        return WebAPIConnection(url, *args, **kwds)
    # Memory URLs use an in-memory sqlite database
    if scheme == "mem":
        backend = SQLBackend("sqlite:///")
        return DirectConnection(backend, *args, **kwds)
    # Anything else must be a database URL.
    backend = SQLBackend(url)
    return DirectConnection(backend, *args, **kwds)


class DirectConnection(object):
    """ISauropodConnection implemented as a direct link to the backend."""

    implements(ISauropodConnection)

    def __init__(self, backend, appid):
        self.backend = backend
        self.appid = appid

    def close(self):
        """Close down the connection."""
        pass

    def start_session(self, credentials, **kwds):
        """Start a data access session."""
        userid = credentials
        return DirectSession(self, userid, **kwds)


class DirectSession(object):
    """ISauropodSession implementation as a direct link to the backend."""

    def __init__(self, store, userid):
        self.store = store
        self.userid = userid

    def close(self):
        """Close down the session."""
        pass

    def getitem(self, key, userid=None, appid=None):
        """Get the item stored under the specified key."""
        if userid is None:
            userid = self.userid
        if appid is None:
            appid = self.store.appid
        return self.store.backend.getitem(appid, userid, key)

    def get(self, key, userid=None, appid=None):
        """Get the value stored under the specified key."""
        return self.getitem(key, userid, appid).value

    def set(self, key, value, userid=None, appid=None, if_match=None):
        """Set the value stored under the specified key."""
        if userid is None:
            userid = self.userid
        if appid is None:
            appid = self.store.appid
        return self.store.backend.set(appid, userid, key, value, if_match)

    def delete(self, key, userid=None, appid=None, if_match=None):
        """Delete the value stored under the specified key."""
        if userid is None:
            userid = self.userid
        if appid is None:
            appid = self.store.appid
        return self.store.backend.set(appid, userid, key, if_match)

    def listkeys(self, start=None, end=None, limit=None, userid=None,
                 appid=None):
        """List the keys available in the bucket."""
        if userid is None:
            userid = self.userid
        if appid is None:
            appid = self.store.appid
        return self.store.backend.listkeys(appid, userid, start, end, limit)


class WebAPIConnection(object):
    """ISauropodConnection implemented by calling the HTTP-based API."""

    implements(ISauropodConnection)

    def __init__(self, store_url, appid, appkey):
        self.store_url = store_url
        self.appid = appid
        self.appkey = appkey

    def close(self):
        """Close down the connection."""
        pass

    def start_session(self, credentials, **kwds):
        """Start a data access session."""
        r = self.request("/session/start", "POST", credentials)
        userid = r.headers["X-Sauropod-UserID"]
        data = cgi.parse_qs(r.content)
        sessionid = data["oauth_token"][-1]
        sessionkey = data["oauth_token_secret"][-1]
        return WebAPISession(self, userid, sessionid, sessionkey, **kwds)

    def request(self, path, method="GET", body="", headers=None, session=None):
        """Make a HTTP request to the Sauropod server, return the result.

        This method is a handy wrapper around the "requests" module that makes
        signed requests to the Sauropod server.  If the request is successful
        then the response body is returned; otherwise a HTTPError is raised.
        """
        if not headers:
            headers = {}
        else:
            headers = headers.copy()
        headers["Content-Length"] = str(len(body))
        # Produce OAuth signature.
        oauth = {}
        oauth["realm"] = "Sauropod"
        oauth["oauth_consumer_key"] = self.appid
        oauth["oauth_signature_method"] = "HMAC-SHA1"
        oauth["oauth_timestamp"] = str(int(time.time()))
        oauth["oauth_nonce"] = os.urandom(6).encode("hex")
        if session is not None:
            oauth["oauth_token"] = session.sessionid
        key = self.appkey
        if session is not None:
            key += "&" + session.sessionkey
        # TODO: actually calculate the string to be signed...
        oauth["oauth_signature"] = b64encode(hmac.new(key, "", sha1).digest())
        oauth = ", ".join("%s=\"%s\"" % item for item in oauth.iteritems())
        oauth = "OAuth " + oauth
        headers["Authorization"] = oauth
        # Send the request.
        url = urljoin(self.store_url, path)
        resp = requests.request(method, url, None, body, headers)
        resp.raise_for_status()
        return resp


class WebAPISession(object):
    """ISauropodSession implemented by calling the HTTP-based API."""

    def __init__(self, store, userid, sessionid, sessionkey):
        self.store = store
        self.userid = userid
        self.sessionid = sessionid
        self.sessionkey = sessionkey

    def close(self):
        """Close down the session."""
        pass

    def request(self, path="", method="GET", body="", headers=None):
        """Make a HTTP request to the Sauropod server, return the result.

        This method is a handy wrapper around the Store.request method, to
        make sure that it uses the correct session for OAuth signing.
        """
        return self.store.request(path, method, body, headers, self)

    def getitem(self, key, userid=None, appid=None):
        """Get the item stored under the specified key."""
        if userid is None:
            userid = self.userid
        if appid is None:
            appid = self.store.appid
        path = "/app/%s/users/%s/keys/%s" % (appid, userid, key)
        try:
            r = self.request(path, "GET")
        except HTTPError, e:
            if e.code == 404:
                raise KeyError(key)
            raise
        return Item(appid, userid, key, r.content, r.headers["ETag"])

    def get(self, key, userid=None, appid=None):
        """Get the value stored under the specified key."""
        return self.getitem(key, userid, appid).value

    def set(self, key, value, userid=None, appid=None, if_match=None):
        """Set the value stored under the specified key."""
        if userid is None:
            userid = self.userid
        if appid is None:
            appid = self.store.appid
        path = "/app/%s/users/%s/keys/%s" % (appid, userid, key)
        headers = {}
        if if_match is not None:
            if if_match == "":
                headers["If-None-Match"] = "*"
            else:
                headers["If-Match"] = if_match
        try:
            self.request(path, "PUT", value, headers)
        except HTTPError, e:
            if e.code == 412:
                raise ConflictError(key)
            raise

    def delete(self, key, userid=None, appid=None, if_match=None):
        """Delete the value stored under the specified key."""
        if userid is None:
            userid = self.userid
        if appid is None:
            appid = self.store.appid
        path = "/app/%s/users/%s/keys/%s" % (appid, userid, key)
        headers = {}
        if if_match is not None:
            if if_match == "":
                headers["If-None-Match"] = "*"
            else:
                headers["If-Match"] = if_match
        try:
            self.request(path, "DELETE", headers=headers)
        except HTTPError, e:
            if e.code == 404:
                raise KeyError(key)
            if e.code == 412:
                raise ConflictError(key)
            raise

    def listkeys(self, start=None, end=None, limit=None, userid=None,
                 appid=None):
        """List the keys available in the bucket."""
        if userid is None:
            userid = self.userid
        if appid is None:
            appid = self.store.appid
        path = "/app/%s/users/%s/keys/" % (appid, userid)
        if start is not None or end is not None or limit is not None:
            args = []
            if start is not None:
                args.append(("start", start))
            if end is not None:
                args.append(("end", end))
            if limit is not None:
                args.append(("limit", limit))
            args = ("%s=%s" % (arg[0], urlquote(str(arg[1]))) for arg in args)
            path += "?" + "&".join(args)
        r = self.request(path, "GET")
        for key in r.content.split("\n"):
            key = urlunquote(key.strip())
            if key:
                yield key

