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

__ver_major__ = 0
__ver_minor__ = 1
__ver_patch__ = 0
__ver_sub__ = ""
__ver_tuple__ = (__ver_major__, __ver_minor__, __ver_patch__, __ver_sub__)
__version__ = "%d.%d.%d%s" % __ver_tuple__


import json
import uuid
from urllib import quote as urlquote
from urllib import unquote as urlunquote
from urlparse import urlparse, urljoin

import requests

from zope.interface import implements

from mozsvc.util import maybe_resolve_name

from pysauropod.interfaces import ISauropodConnection, ISauropodSession, Item
from pysauropod.backends.sql import SQLBackend
from pysauropod.errors import (Error,  # NOQA
                               ConnectionError,
                               ServerError,
                               ServerBusyError,
                               ConflictError,
                               AuthenticationError)

# The requests module has a bug that makes it unable to access urls
# containing a quoted slash. Monkey-patch until fix is released.
if requests.__build__ <= 0x000801:
    import requests.models
    import urllib

    class monkey_patched_urllib(object):

        def __getattr__(self, name):
            return getattr(urllib, name)

        def quote(self, s):
            # Don't re-quote slashes if they're already quoted.
            return "%2F".join(urlquote(part) for part in s.split("%2F"))

        def unquote(self, s):
            # Don't unquote slashes if they're already quoted.
            return "%2F".join(urlunquote(part) for part in s.split("%2F"))

    requests.models.urllib = monkey_patched_urllib()


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
    backend = SQLBackend(url, create_tables=kwds.pop("create_tables", False))
    return DirectConnection(backend, *args, **kwds)


class DirectConnection(object):
    """ISauropodConnection implemented as a direct link to the backend."""

    implements(ISauropodConnection)

    def __init__(self, backend, appid, verifier=None):
        if verifier is None:
            verifier = "vep:RemoteVerifier"
        verifier = maybe_resolve_name(verifier)
        if callable(verifier):
            verifier = verifier()
        self._verifier = verifier
        self.backend = backend
        self.appid = appid

    def close(self):
        """Close down the connection."""
        pass

    def start_session(self, userid, credentials, **kwds):
        """Start a data access session."""
        try:
            email = self._verifier.verify(**credentials)["email"]
        except (ValueError, vep.TrustError):
            raise AuthenticationError("invalid credentials")
        return DirectSession(self, userid, uuid.uuid4().hex, **kwds)

    def resume_session(self, userid, sessionid, **kwds):
        """Resume a data access session."""
        return DirectSession(self, userid, sessionid, **kwds)


class DirectSession(object):
    """ISauropodSession implementation as a direct link to the backend."""

    implements(ISauropodSession)

    def __init__(self, store, userid, sessionid):
        self.store = store
        self.userid = userid
        self.sessionid = sessionid

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
        return self.store.backend.delete(appid, userid, key, if_match)


class WebAPIConnection(object):
    """ISauropodConnection implemented by calling the HTTP-based API."""

    implements(ISauropodConnection)

    def __init__(self, store_url, appid):
        self.store_url = store_url
        self.appid = appid
        self._reqpool = requests.session()

    def close(self):
        """Close down the connection."""
        pass

    def start_session(self, userid, credentials, **kwds):
        """Start a data access session."""
        r = self.request("/session/start", "POST", credentials)
        sessionid = r.content
        return WebAPISession(self, userid, sessionid, **kwds)

    def resume_session(self, userid, sessionid, **kwds):
        """Resume a data access session."""
        return WebAPISession(self, userid, sessionid, **kwds)

    def request(self, path, method="GET", data="", headers=None, session=None):
        """Make a HTTP request to the Sauropod server, return the result.

        This method is a handy wrapper around the "requests" module that makes
        signed requests to the Sauropod server.  It returns a response object.
        """
        if not headers:
            headers = {}
        else:
            headers = headers.copy()
        if session is not None:
            headers["Signature"] = session.sessionid
        # Send the request.
        url = urljoin(self.store_url, path)
        try:
            r = self._reqpool.request(method, url, None, data, headers)
        except requests.RequestException, e:
            raise ConnectionError(*e.args)
        # Greedily load the body content.
        # This ensures the connection can be put back in the pool.
        r.content
        # If that was an error, translate it into one of our internal types.
        # 401 or 403 indicate that authentication failed.
        if r.status_code in (401, 403):
            raise AuthenticationError("invalid credentials")
        # 412 indicates an etag conflict.
        if r.status_code == 412:
            raise ConflictError("if_match was not satisfied")
        # 503 indicates the server is too busy.
        if r.status_code == 503:
            try:
                retry_after = int(r.headers["Retry-After"])
            except (KeyError, ValueError, TypeError):
                retry_after = None
            raise ServerBusyError(r.content, r.status_code, retry_after)
        # All other failures just turn into a generic ServerError.
        if r.status_code < 200 or r.status_code >= 300:
            raise ServerError(r.content, r.status_code)
        return r


class WebAPISession(object):
    """ISauropodSession implemented by calling the HTTP-based API."""

    implements(ISauropodSession)

    def __init__(self, store, userid, sessionid):
        self.store = store
        self.userid = userid
        self.sessionid = sessionid

    def close(self):
        """Close down the session."""
        pass

    def request(self, path="", method="GET", data="", headers=None):
        """Make a HTTP request to the Sauropod server, return the result.

        This method is a handy wrapper around the Store.request method, to
        make sure that it uses the correct session for OAuth signing.
        """
        return self.store.request(path, method, data, headers, self)

    def keypath(self, key, userid=None, appid=None):
        """Get the server path at which to access the given key."""
        if userid is None:
            userid = self.userid
        if appid is None:
            appid = self.store.appid
        path = "/app/%s/users/%s/keys/%s"
        path = path % tuple(urlquote(v, safe="") for v in (appid, userid, key))
        return path

    def getitem(self, key, userid=None, appid=None):
        """Get the item stored under the specified key."""
        path = self.keypath(key, userid, appid)
        try:
            r = self.request(path, "GET")
        except ServerError, e:
            if e.status_code == 404:
                raise KeyError(key)
            raise
        value = json.loads(r.content)["value"]
        return Item(appid, userid, key, value, r.headers.get("ETag"))

    def get(self, key, userid=None, appid=None):
        """Get the value stored under the specified key."""
        return self.getitem(key, userid, appid).value

    def set(self, key, value, userid=None, appid=None, if_match=None):
        """Set the value stored under the specified key."""
        path = self.keypath(key, userid, appid)
        headers = {}
        if if_match is not None:
            if if_match == "":
                headers["If-None-Match"] = "*"
            else:
                headers["If-Match"] = if_match
        r = self.request(path, "PUT", dict(value=value), headers)
        return Item(appid, userid, key, value, r.headers.get("ETag"))

    def delete(self, key, userid=None, appid=None, if_match=None):
        """Delete the value stored under the specified key."""
        path = self.keypath(key, userid, appid)
        headers = {}
        if if_match is not None:
            if if_match == "":
                headers["If-None-Match"] = "*"
            else:
                headers["If-Match"] = if_match
        try:
            self.request(path, "DELETE", headers=headers)
        except ServerError, e:
            if e.status_code == 404:
                raise KeyError(key)
            raise
