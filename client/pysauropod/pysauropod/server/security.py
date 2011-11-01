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

Security-related code for the minimal sauropod server.

"""

import time
import threading
import heapq
import hmac
from hashlib import sha1
from base64 import b64encode

from zope.interface import implements

from pyramid.security import Everyone, Authenticated
from pyramid.interfaces import IAuthenticationPolicy, IAuthorizationPolicy

from pysauropod.server.session import IAppSessionDB
from pysauropod.server.utils import strings_differ, parse_authz_header


def includeme(config):
    """Include the sauropod security definitions in a pyramid config.

    Including "pysauropod.server.security" will get you the following:

        * a root_factory that identifies the appid and userid for each request
        * an authorization policy that defines some handy permissions
        * an authentication policy that handles auth via OAuth header data

    """
    config.set_root_factory(SauropodContext)
    config.set_authentication_policy(SauropodAuthenticationPolicy())
    config.set_authorization_policy(SauropodAuthorizationPolicy())


class SauropodContext(object):
    """Custom request context for Sauropod.

    This context takes the associated appid and userid from the request
    so that they're available for permission checking.
    """
    def __init__(self, request):
        self.request = request
        if request.matchdict is None:
            self.appid = None
            self.userid = None
        else:
            self.appid = request.matchdict.get("appid", None)
            self.userid = request.matchdict.get("userid", None)


class SauropodAuthorizationPolicy(object):
    """Custom authorization policy for Sauropod.

    This policy provides pre-built permissions to identify valid appids,
    as well as getting, setting and deleting keys.
    """
    implements(IAuthorizationPolicy)

    def permits(self, context, principals, permission):
        # The "valid-app" permission matches anything with a valid appid.
        if permission == "valid-app":
            for principal in principals:
                if principal.startswith("app:"):
                    return True
            return False
        # The "this-app" permission matches the appid of the context.
        if permission == "this-app":
            if context.appid is None:
                return False
            principal = "app:" + context.appid
            return (principal in principals)
        # The "*-key" permissions match appid and userid of the context.
        if permission in ("get-key", "set-key", "del-key"):
            if context.appid is None or context.userid is None:
                return False
            principal = "app:" + context.appid
            return (principal in principals and context.userid in principals)
        # No other permissions are defined.
        return False


class SauropodAuthenticationPolicy(object):
    """Custom authentication policy for Sauropod.

    This policy identifies the request primarily by the userid associated
    with the session, but it also provides an extra principal to identify
    the requesting application.

    Request signing is done as standard OAuth-v1 signatures, with parameters
    transmitted in the Authorization header, and with the following mapping
    from OAuth terminology to Sauropod terminology:

        * oauth_consumer_key:  appid
        * oauth_token:         sessionid

    """
    implements(IAuthenticationPolicy)

    def __init__(self, nonce_timeout=None):
        if nonce_timeout is None:
            nonce_timeout = 5 * 60
        self.nonce_timeout = nonce_timeout
        self.nonce_cache = NonceCache(nonce_timeout)

    def authenticated_userid(self, request):
        """Get the userid associated with this request.

        This method checks the OAuth signature dat and, if it's valid and
        has a session, returns associated userid.  Note that it's possible
        for a request to be authenticated but not have a userid (such a
        a request has yet to establish a session).
        """
        authz = self._get_auth_data(request)
        if authz is None:
            return None
        return authz.get("userid", None)
        
    def unauthenticated_userid(self, request):
        """Get the userid associated with this request.

        For Sauropod this method is exactly equivalent to the authenticated
        version - since loading data from the session means consulting the
        AppSesssionDB, there's no point in trying to shortcut any validation
        of the signature.
        """
        return self.authenticated_userid(request)

    def effective_principals(self, request):
        """Get the effective principals active for this request.

        For authenticated requests, the effective principals will always
        include the application if in the form "app:APPID".  If the request
        has a valid session then it will also include the associated userid.
        """
        principals = [Everyone]
        authz = self._get_auth_data(request)
        if authz is not None:
            principals.append(Authenticated)
            principals.append("app:" + authz["appid"])
            if "userid" in authz:
                principals.append(authz["userid"])
        return principals

    def remember(self, request, principal):
        """Remember the authenticated user.

        This is a no-op for Sauropod; clients must remember their credentials
        and include a valid signature on every request.
        """
        return []

    def forget(self, request):
        """Forget the authenticated user.

        This is a no-op for Sauropod; clients must remember their credentials
        and include a valid signature on every request.
        """
        return []
 
    def _get_auth_data(self, request):
        """Get the authentication data from the request.

        This method checks the OAuth signature in the request.  If invalid
        then None is returned; if valid then a dict giving the appid and
        possible the userid is returned.
        """
        # Try to use cached version.
        if "sauropod.auth_data" in request.environ:
            return request.environ["sauropod.auth_data"]
        # Grab the OAuth credentials from the request.
        params = self._get_authz_params(request)
        if params is None:
            return None
        appid = params["oauth_consumer_key"]
        sessionid = params.get("oauth_token", None)
        # Validate the OAuth signature.
        sigdata = self._calculate_sigdata(request)
        sessiondb = request.registry.getUtility(IAppSessionDB)
        sigkey = sessiondb.get_app_key(appid)
        if sessionid is not None:
            sigkey += "&" + sessiondb.get_session_key(appid, sessionid)
        expected_sig = b64encode(hmac.new(sigkey, sigdata, sha1).digest())
        if strings_differ(params["oauth_signature"], expected_sig):
            return None
        # Cache the nonce to avoid re-use.
        # We do this *after* successul auth to avoid DOS attacks.
        nonce = params["oauth_nonce"]
        timestamp = int(params["oauth_timestamp"])
        self.nonce_cache.add(nonce, timestamp)
        # Load the session from the database if needed
        authz = {"appid": appid}
        if sessionid is not None:
            authz["userid"] = sessiondb.get_session_data(appid, sessionid)
        request.environ["sauropod.auth_data"] = authz
        return authz
        
    def _get_authz_params(self, request):
        """Parse, validate and return the request Authorization header.

        This method grabs the OAuth credentials from the Authorization header
        and performs some sanity-checks.  If the credentials are missing or
        malformed then it returns None; if they're ok then they are returned
        in a dict.

        Note that this method does *not* validate the OAuth signature.
        """
        params = parse_authz_header(request, None)
        if params is None:
            return None
        # Check that various parameters are as expected.
        if params.get("scheme", None) != "OAuth":
            return None
        if params.get("realm", None) != "Sauropod":
            return None
        if params.get("oauth_signature_method", None) != "HMAC-SHA1":
            return None
        if "oauth_consumer_key" not in params:
            return None
        # Check the timestamp, reject if too far from current time.
        try:
            timestamp = int(params["oauth_timestamp"])
        except (KeyError, ValueError):
            return None
        if abs(timestamp - time.time()) >= self.nonce_timeout:
            return None
        # Check that the nonce is not being re-used.
        nonce = params.get("oauth_nonce", None)
        if nonce is None:
            return None
        if nonce in self.nonce_cache:
            return None
        # OK, they seem like sensible OAuth paramters.
        return params

    def _calculate_sigdata(self, request):
        """Get the data to be signed for OAuth authentication.

        This method takes a request object and returns the data that should
        be signed for OAuth authentication of that request.  This data is the
        "signature base string" as defined in section 3.4.1 of RFC-5849.
        """
        # TODO: actually implement this
        return ""


class NonceCache(object):
    """Object for managing a short-lived cache of nonce values.

    This class allow easy management of client-generated nonces.  It keeps
    a set of seen nonce values so that they can be looked up quickly, and
    a queue ordering them by timestamp so that they can be purged when
    they expire.
    """

    def __init__(self, timeout=None):
        if timeout is None:
            timeout = 5 * 60
        self.timeout = timeout
        self.nonces = set()
        self.purge_lock = threading.Lock()
        self.purge_queue = []

    def __contains__(self, nonce):
        """Check if the given nonce is in the cache."""
        return (nonce in self.nonces)

    def add(self, nonce, timestamp):
        """Add the given nonce to the cache."""
        with self.purge_lock:
            # Purge a few expired nonces to make room.
            # Don't purge *all* of them, since we don't want to pause too long.
            purge_deadline = time.time() - self.timeout
            try:
                for _ in xrange(5):
                    (old_timestamp, old_nonce) = self.purge_queue[0]
                    if old_timestamp >= purge_deadline:
                        break
                    self.nonces.remove(old_nonce)
                    heapq.heappop(self.purge_queue)
            except (IndexError, KeyError):
                pass
            # Add the new nonce into queue and map.
            heapq.heappush(self.purge_queue, (timestamp, nonce))
            self.nonces.add(nonce)
