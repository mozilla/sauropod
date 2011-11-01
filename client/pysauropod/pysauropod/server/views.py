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

Views for minimal sauropod server.

"""

from pyramid.security import effective_principals
from pyramid.response import Response
from pyramid.httpexceptions import (HTTPNoContent, HTTPNotFound,
                                    HTTPForbidden, HTTPUnprocessableEntity)

from cornice import Service

from pysauropod.server.storage import IStorageDB
from pysauropod.server.session import IAppSessionDB
from pysauropod.server.utils import verify_browserid

start_session = Service(name="start_session", path="/session/start")
keys = Service(name="keys", path="/app/{appid}/users/{userid}/keys/")
key = Service(name="key", path="/app/{appid}/users/{userid}/keys/{key}")


@start_session.post(permission="valid-app")
def create_session(request):
    """Create a new session.

    You must specify a set of credentials in the POST body.  These will be
    validated to obtain a userid and a new session will be started tied to
    that userid.

    The response will contain OAuth token details for the new session.
    """
    for principal in effective_principals(request):
        if principal.startswith("app:"):
            appid = principal[4:]
            break
    # The request must post a valid BrowserID assertion and audience.
    # TODO: should I be checking the audience against something internal?
    #assertion = request.POST.get("assertion")
    #audience = request.POST.get("audience")
    #if assertion is None or audience is None:
    #    raise HTTPUnprocessableEntity()
    #if not verify_browserid(assertion, audience):
    #    raise HTTPForbidden()
    userid = request.body
    # Create the session, return the necessary keys.
    sessiondb = request.registry.getUtility(IAppSessionDB)
    sessionid = sessiondb.new_session(appid, userid)
    sessionkey = sessiondb.get_session_key(appid, sessionid)
    response = "oauth_token=%s&oauth_token_secret=%s"
    response = response % (sessionid, sessionkey)
    return Response(response, content_type="application/x-www-form-urlencoded")


@keys.get(permission="get-key", renderer="json")
def list_keys(request):
    """List keys for the given user.

    You must have a valid session and be authenticated as the target user.
    """
    appid = request.matchdict["appid"]
    userid = request.matchdict["userid"]
    prefix = request.GET.get("prefix", None)
    store = request.registry.queryUtility(IStorageDB)
    return list(store.listkeys(appid, userid, prefix))


@key.get(permission="get-key")
def get_key(request):
    """Get the value of a key.

    You must have a valid session and be authenticated as the target user.
    """
    appid = request.matchdict["appid"]
    userid = request.matchdict["userid"]
    key = request.matchdict["key"]
    store = request.registry.queryUtility(IStorageDB)
    try:
        value = store.get(appid, userid, key)
    except KeyError:
        raise HTTPNotFound()
    else:
        return Response(value, content_type="application/octet-stream")


@key.put(permission="set-key")
def set_key(request):
    """Update the value of a key.

    You must have a valid session and be authenticated as the target user.
    """
    appid = request.matchdict["appid"]
    userid = request.matchdict["userid"]
    key = request.matchdict["key"]
    store = request.registry.queryUtility(IStorageDB)
    store.set(appid, userid, key, request.body)
    return HTTPNoContent()


@key.delete(permission="del-key")
def delete_key(request):
    """Delete a key.

    You must have a valid session and be authenticated as the target user.
    """
    appid = request.matchdict["appid"]
    userid = request.matchdict["userid"]
    key = request.matchdict["key"]
    store = request.registry.queryUtility(IStorageDB)
    try:
        store.delete(appid, userid, key)
    except KeyError:
        raise HTTPNotFound()
    return HTTPNoContent()
