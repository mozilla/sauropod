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

Credential-checking code for the minimal sauropod server.

"""

import urllib2
import json


from zope.interface import implements, Interface

from mozsvc import plugin


def includeme(config):
    """Include the default credential-checking definitions.

    Call this function on a pyramid configurator to register a utility for
    the ICredentialChecker interface.  The particular implementation to use
    will  be taken from the configurator settings dict, falling back to a
    BrowserID-based scheme as the default.
    """
    settings = config.get_settings()
    if "sauropod.credentials.backend" not in settings:
#        default_backend = "pysauropod.server.credentials.BrowserIDCredentials"
        default_backend = "pysauropod.server.credentials.DummyCredentials"
        settings["sauropod.credentials.backend"] = default_backend
    plugin.load_and_register("sauropod.credentials", config)


class ICredentialsManager(Interface):
    """Interface for implementing credentials-checking."""

    def check_credentials(credentials):
        """Check the given credentials.

        This method checks the given dict of credentials.  If valid then it
        returns an (appid, userid) tuple; if invalid then it returns a tuple
        of two Nones.
        """


class DummyCredentials(object):
    """Credentials-checking that just accepts any old thing.

    This class implements the ICredentialsManager interface for testhing
    purposes.  It accepts appid and userid in the credentials and will
    happily just return them a valid.
    """
    implements(ICredentialsManager)

    def check_credentials(self, credentials):
        appid = credentials.get("audience")
        if appid is not None:
            appid = appid.encode("utf8")
        userid = credentials.get("assertion")
        if userid is not None:
            userid = userid.encode("utf8")
        return (appid, userid)


class BrowserIDCredentials(object):
    """Credentials-checking based on BrowserID.

    This class implements the ICredentialsManager interface using browserid
    assertions as the credentials.  The appid is the assertion audience, the
    userid is the asserted email address.
    """
    implements(ICredentialsManager)

    def check_credentials(self, credentials):
        assertion = credentials.get("assertion")
        audience = credentials.get("audience")
        if assertion is None or audience is None:
            return (None, None)
        userid = verify_browserid(assertion, audience)
        if userid is None:
            return (None, None)
        return (audience, userid)


def verify_browserid(assertion, audience):
    """Verify the given BrowserID assertion.

    This function verifies the given BrowserID assertion.  It returns the
    asserted email address is valie, None otherwise.  It currently just POSTs
    to the browserid.org verifier service.

    WARNING: this does no HTTPS certificate checking and so is completely open
             to credential forgery.  I'll fix that eventually...

    """
    post_data = "assertion=%s&audience=%s" % (assertion, audience)
    try:
        resp = urllib2.urlopen("https://browserid.org/verify", post_data)
        content_length = resp.info().get("Content-Length")
        if content_length is None:
            data = resp.read()
        else:
            data = resp.read(int(content_length))
        data = json.loads(data)
    except (ValueError, IOError):
        return False
    if data.get("status") != "okay":
        return None
    if data.get("audience") != audience:
        return None
    return data.get("email")
