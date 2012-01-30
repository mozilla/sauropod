# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.
"""

Views for Sauropod Web-API server.

"""

import json
from urllib import quote as urlquote

from pyramid.response import Response
from pyramid.httpexceptions import (HTTPNoContent, HTTPNotFound,
                                    HTTPForbidden, HTTPBadRequest,
                                    HTTPPreconditionFailed)

from cornice import Service

from pysauropod.errors import ConflictError
from pysauropod.interfaces import ISauropodBackend
from pysauropod.server.session import ISessionManager
from pysauropod.server.credentials import ICredentialsManager


start_session = Service(name="start_session", path="/session/start")
keys = Service(name="keys", path="/app/{appid}/users/{userid}/keys/")
key = Service(name="key", path="/app/{appid}/users/{userid}/keys/{key}")


@start_session.post()
def create_session(request):
    """Create a new session.

    You must specify a set of credentials in the POST body.  These will be
    validated to obtain a userid and a new session will be started tied to
    that userid.

    The response will contain token details for the new session.
    """
    # Check the credentials with the registered manager.
    credsdb = request.registry.getUtility(ICredentialsManager)
    appid, userid = credsdb.check_credentials(dict(request.POST))
    if appid is None or userid is None:
        raise HTTPForbidden()
    # Create the session, return the id for future requests.
    sessiondb = request.registry.getUtility(ISessionManager)
    sessionid = sessiondb.new_session(appid, userid)
    r = Response(sessionid, content_type="text/plain")
    return r


@keys.get(permission="get-key")
def list_keys(request):
    """List keys for the given user.

    You must have a valid session and be authenticated as the target user.
    """
    appid = request.matchdict["appid"].encode("utf8")
    userid = request.matchdict["userid"].encode("utf8")
    start = request.GET.get("start", None)
    end = request.GET.get("end", None)
    limit = request.GET.get("limit", None)
    if limit:
        try:
            limit = int(limit)
        except ValueError:
            raise HTTPBadRequest()
    store = request.registry.getUtility(ISauropodBackend)
    keys = store.listkeys(appid, userid, start, end, limit)
    response = "\n".join(urlquote(key) for key in keys)
    r = Response(response, content_type="application/newlines")
    return r


@key.get(permission="get-key")
def get_key(request):
    """Get the value of a key.

    You must have a valid session and be authenticated as the target user.
    """
    appid = request.matchdict["appid"].encode("utf8")
    userid = request.matchdict["userid"].encode("utf8")
    key = request.matchdict["key"].encode("utf8")
    store = request.registry.getUtility(ISauropodBackend)
    try:
        item = store.getitem(appid, userid, key)
    except KeyError:
        raise HTTPNotFound()
    r = Response(_item_to_json(item), content_type="application/json")
    if item.etag:
        r.headers["ETag"] = item.etag
    return r


@key.put(permission="set-key")
def set_key(request):
    """Update the value of a key.

    You must have a valid session and be authenticated as the target user.
    """
    appid = request.matchdict["appid"].encode("utf8")
    userid = request.matchdict["userid"].encode("utf8")
    key = request.matchdict["key"].encode("utf8")
    store = request.registry.getUtility(ISauropodBackend)
    value = request.POST.get("value")
    if value is None:
        raise HTTPBadRequest("mising value")
    if_match = _get_if_match(request)
    try:
        item = store.set(appid, userid, key, value, if_match=if_match)
    except ConflictError:
        raise HTTPPreconditionFailed()
    r = HTTPNoContent()
    if item.etag:
        r.headers["ETag"] = item.etag
    return r


@key.delete(permission="del-key")
def delete_key(request):
    """Delete a key.

    You must have a valid session and be authenticated as the target user.
    """
    appid = request.matchdict["appid"].encode("utf8")
    userid = request.matchdict["userid"].encode("utf8")
    key = request.matchdict["key"].encode("utf8")
    if_match = _get_if_match(request)
    store = request.registry.getUtility(ISauropodBackend)
    try:
        store.delete(appid, userid, key, if_match=if_match)
    except KeyError:
        raise HTTPNotFound()
    except ConflictError:
        raise HTTPPreconditionFailed()
    return HTTPNoContent()


def _item_to_json(item):
    """Render an Item as a json dict."""
    data = {}
    data["key"] = item.key
    data["value"] = item.value
    data["user"] = item.userid
    data["bucket"] = item.appid
    data["timestamp"] = 0
    return json.dumps(data)


def _get_if_match(request):
    """Get the if_match value from a request."""
    if_match = request.headers.get("If-Match", None)
    if if_match is None:
        if_match = request.headers.get("If-None-Match", None)
        if if_match is not None:
            if if_match != "*":
                # I have no way to process if-none-match=some-etag.
                # Don't do that, OK?
                raise HTTPBadRequest()
            if_match = ""
    return if_match
