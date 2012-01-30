# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.
"""

Security-related code for the Sauropod webapi server.

"""

from zope.interface import implements

from pyramid.security import Everyone, Authenticated
from pyramid.interfaces import IAuthenticationPolicy, IAuthorizationPolicy

from pysauropod.server.session import ISessionManager


def includeme(config):
    """Include the sauropod security definitions in a pyramid config.

    Including "pysauropod.backends.webapi.server.security" will get you the
    following:

        * a root_factory that identifies the appid and userid for each request
        * an authorization policy that defines some handy permissions
        * an authentication policy that handles auth via OAuth header data

    """
    config.set_root_factory(SauropodContext)
    config.set_authorization_policy(SauropodAuthorizationPolicy())
    config.set_authentication_policy(SauropodAuthenticationPolicy())


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

    Requests are currently authenticated using a simple bearer-token scheme,
    with each request embedding the sessionid under which it wants to operate.
    Eventually we'll implement something like 2-legged OAuth signing.
    """
    implements(IAuthenticationPolicy)

    def authenticated_userid(self, request):
        """Get the userid associated with this request.

        This method checks the embedded request signature and, if it contains
        a valid session, returns the associated userid.
        """
        session = self._get_session_data(request)
        if session is None:
            return None
        return session[1]

    def unauthenticated_userid(self, request):
        """Get the userid associated with this request.

        For Sauropod this method is exactly equivalent to the authenticated
        version - since loading data from the session means consulting the
        ISesssionManager, there's no point in trying to shortcut any validation
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
        session = self._get_session_data(request)
        if session is not None:
            appid, userid = session
            principals.append(Authenticated)
            principals.append(userid)
            principals.append("app:" + appid)
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

    def _get_session_data(self, request):
        """Get the session data from the request.

        This method checks the session identifier included in the request.
        If invalid then None is returned; if valid then the (appid, userid)
        tuple is returned.
        """
        # Try to use cached version.
        if "sauropod.session_data" in request.environ:
            return request.environ["sauropod.session_data"]
        # Grab the sessionid from the "signature" heaer.
        sessionid = request.environ.get("HTTP_SIGNATURE")
        if sessionid is None:
            return None
        session_manager = request.registry.getUtility(ISessionManager)
        session = session_manager.get_session_data(sessionid)
        request.environ["sauropod.session_data"] = session
        return session
