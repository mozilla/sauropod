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

Python client for the Sauropod data store.

"""


import os
import cgi
import time
import json
import httplib
import hmac
from hashlib import sha1
from base64 import b64encode
from urlparse import urlparse


class Error(Exception):
    """Base error type for pysauropod."""
    pass


class ServerError(Exception):
    """Base class for errors raised by the server."""
    def __init__(self, message, status):
        self.status = status
        super(ServerError, self).__init__(message)


class Store(object):
    """Top-level reference to a Sauropod data store.

    This class encapsulates the high-level connection information for a 
    Sauropod data store.  It must be given the URL of the storage server
    and the application ID and key to be used to access it.

    All actual storage operations must be done through a "Session" object,
    which accesses the store as a particular user.  Use the "start_session"
    method to obtain one.
    """

    def __init__(self, store_url, appid, appkey):
        self.store_url = store_url
        self.store_url_p = urlparse(store_url)
        self.appid = appid
        self.appkey = appkey

    def close(self):
        """Close down the store.

        This method releases any resources held by the store (e.g. persistent
        connections) and tears down the internal state.  You should not try
        to use a Store after it has been closed.
        """
        pass

    def start_session(self, credentials, **kwds):
        """Start a data access session.

        This method starts a data access session as the user specified in the
        given credentials.  The data available will depend on the data and
        permissions of that user.
        """
        data = self.request("/session/start", "POST", credentials)
        data = cgi.parse_qs(data)
        sessionid = data["oauth_token"][-1]
        sessionkey = data["oauth_token_secret"][-1]
        return Session(self, sessionid, sessionkey, credentials, **kwds)

    def request(self, path, method="GET", body="", headers=None, session=None):
        """Make a HTTP request to the Sauropod server, return the result.

        This method is a handy wrapper around httplib that makes signed
        requests to the Sauropod server.  If the request is successful then
        the response body is returned; otherwise a ServerError is raised.
        """
        # TODO: this is nice to start, but will get unwieldy when we try
        #       to add nifty stuff like persistent connections.  Shall we
        #       just drop in the "requests" module here?
        if headers is None:
            headers = []
        else:
            if hasattr(headers, "iteritems"):
                headers = list(headers.iteritems())
            else:
                headers = list(headers)
        headers.append(("Content-Length", len(body)))
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
        headers.append(("Authorization", oauth))
        # Send the request.
        resp = None
        con = httplib.HTTPConnection(self.store_url_p.hostname,
                                     self.store_url_p.port)
        con.connect()
        try:
            con.putrequest(method, self.store_url_p.path + path)
            for name, value in headers:
                con.putheader(name, value)
            con.endheaders()
            con.send(body)
            # Get the response, check for errors.
            resp = con.getresponse()
            if resp.status < 200 or resp.status >= 300:
                message = "%d %s" % (resp.status, resp.reason)
                raise ServerError(message, resp.status)
            # Read the body, being careful not to read past content-length.
            content_length = None
            for name, value in resp.getheaders():
                if name.lower() == "content-length":
                    try:
                        content_length = int(value)
                    except ValueError:
                        pass
            if content_length is None:
                data = resp.read()
            else:
                data = resp.read(content_length)
            return data
        finally:
            if resp is None:
                resp.close()
            con.close()


class Session(object):
    """Interface to a per-user data access session.

    This class encapsulates access to Sauropod data in the context of a
    specific user.  It allows you to get, put and delete keys by name,
    assuming that the user has appropriate permissions.

    Each session has two associated user identifiers:

      * The "active userid" is the user as which the session is authenticated,
        i.e. the userid whose credentials were provided at creation time.

      * The "default userid" is the user whose keyspace will be accessed when
        get/put/delete are not given an explicit userid.  Often this will be
        the same as the active userid, but it need not be.

    To help applications segregate their keys, you may also specify a key
    prefix which will be appended to all keys prior to talking to the server.
    """

    def __init__(self, store, sessionid, sessionkey, active_userid,
                 default_userid=None, prefix=None):
        if default_userid is None:
            default_userid = active_userid
        self.store = store
        self.sessionid = sessionid
        self.sessionkey = sessionkey
        self.active_userid = active_userid
        self.default_userid = default_userid
        self.prefix = prefix

    def close(self):
        """Close down the session.

        This method releases any resources held by the session (e.g. persistent
        connections) and tears down the internal state.  You should not try
        to use a Session after it has been closed.
        """
        pass

    def request(self, path="", method="GET", body="", headers=None):
        """Make a HTTP request to the Sauropod server, return the result.

        This method is a handy wrapper around the Store.request method, to
        make sure that it uses the correct session for OAuth signing.
        """
        return self.store.request(path, method, body, headers, self)

    def get(self, key, userid=None):
        """Get the value stored under the specified key.

        This method takes the name of a key and retreives the string value
        that is stored there.

        By default the keyspace for the active user is accessed.  Use the
        optional argument "userid" to access the keys of a different user
        (assuming, of course, that the active user has permission to view
        that key for the specified user).
        """
        if self.prefix is not None:
            key = self.prefix + key
        if userid is None:
            userid = self.default_userid
        path = "/app/%s/users/%s/keys/%s" % (self.store.appid, userid, key)
        try:
            return self.request(path, "GET")
        except ServerError, e:
            if e.status == 404:
                raise KeyError(key)
            raise

    def set(self, key, value, userid=None):
        """Set the value stored under the specified key.

        This method takes the name of a key and a string value, and stores the
        value under the specified key.

        By default the keyspace for the active user is accessed.  Use the
        optional argument "userid" to access the keys of a different user
        (assuming, of course, that the active user has permission to set
        that key for the specified user).
        """
        if self.prefix is not None:
            key = self.prefix + key
        if userid is None:
            userid = self.default_userid
        path = "/app/%s/users/%s/keys/%s" % (self.store.appid, userid, key)
        self.request(path, "PUT", value)

    def delete(self, key, userid=None):
        """Delete the value stored under the specified key.

        This method takes the name of a key and deletes the value currently
        stored under that key.

        By default the keyspace for the active user is accessed.  Use the
        optional argument "userid" to delete the keys of a different user
        (assuming, of course, that the active user has permission to delete
        that key for the specified user).
        """
        if self.prefix is not None:
            key = self.prefix + key
        if userid is None:
            userid = self.default_userid
        path = "/app/%s/users/%s/keys/%s" % (self.store.appid, userid, key)
        try:
            self.request(path, "DELETE")
        except ServerError, e:
            if e.status == 404:
                raise KeyError(key)
            raise

    def listkeys(self, prefix=None, userid=None):
        """List the keys available in the store.

        This method returns an iterator yielding key names available in the
        store.  By default it will iterate over all keys; pass in the optional
        argument "prefix" to limit to only keys starting with that prefix.

        By default the keyspace for the active user is accessed.  Use the
        optional argument "userid" to delete the keys of a different user
        (assuming, of course, that the active user has permission to view
        each key for the specified user).
        """
        if prefix is None:
            prefix = ""
        if self.prefix is not None:
            prefix = self.prefix + prefix
        if userid is None:
            userid = self.default_userid
        path = "/app/%s/users/%s/keys/" % (self.store.appid, userid)
        path += "?prefix=" + prefix
        data = self.request(path, "GET")
        for key in json.loads(data):
            if self.prefix is not None:
                key = key[len(self.prefix):]
            yield key


if __name__ == "__main__":
    s = Store("http://localhost:8080", "APP", "APPKEY").start_session("rfk")
    s.set("hello", "world")
    print "hello", s.get("hello")
    s.delete("hello")

