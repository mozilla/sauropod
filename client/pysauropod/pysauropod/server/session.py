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

Session-storage-related code for the minimal sauropod server.

"""

import os
import time
import hashlib
import hmac
import math
from base64 import urlsafe_b64encode as b64encode

from zope.interface import implements, Interface

from pysauropod.server.utils import strings_differ


def includeme(config):
    """Include the default app-session-management definitions."""
    session = SignedAppSessionDB()
    def register():
        config.registry.registerUtility(session, IAppSessionDB)
    config.action(IAppSessionDB, register)


class IAppSessionDB(Interface):
    """Interface for implementing application-session-management."""

    def get_app_key(self, appid):
        """Get the secret signing key for the given application ID."""

    def get_session_key(self, appid, sessionid):
        """Get the secret signing key for the given session ID."""

    def new_session(appid, data):
        """Create a new session and associated the given string data.

        This method creates a new session and associated with it the given
        data.  The sessionid is returned.
        """

    def get_session_data(appid, sessionid):
        """Load the string data associated with the given session.

        This method retrieves the data previously associated with the given
        sessionid and returns it as a string.
        """


class SignedAppSessionDB(object):
    """Application-session-management based on signed tokens.

    This class implements the IAppSessionDB interface using signed session
    tokens.  It's not really a "database" since it doesn't actually store
    the session data anywhere - rather it incorporates it into the token
    in a way that cannot be forged.
    """
    implements(IAppSessionDB)

    def __init__(self, secret=None, timeout=None):
        if secret is None:
            secret = os.urandom(16)
        if timeout is None:
            timeout = 5 * 60
        self.secret = secret
        self.timeout = timeout
        # Since we need to use HMAC for both key-generation and key-signing,
        # generate separate keys for the two operations.  This will help
        # us avoid accidentally turning into e.g. a signature oracle.
        self._sig_key = HKDF_extract("SIGN", secret)
        self._gen_key = HKDF_extract("GENERATE", secret)

    def get_app_key(self, appid):
        """Get the secret signing key for the given application ID.

        In this implementation, the appkey is derived via HKDF-expand from
        the appid and our master key-generation secret.
        """
        # For testing purposes, justuse "APPKEY" for all apps.
        return "APPKEY"
        return HKDF_expand(self._gen_key, appid, 16).encode("hex")

    def get_session_key(self, appid, sessionid):
        """Get the secret signing key for the given session ID.

        In this implementation, the session key is derived via HKDF-expand
        from the sessionid and our master key-generation secret.
        """
        info = "%s&%s" % (appid, sessionid)
        return HKDF_expand(self._gen_key, info, 16).encode("hex")

    def new_session(self, appid, data):
        """Create a new session and associated the given string data.

        In the implementation the session data is actually encoded into the
        sessionid itself, so we don't have to store anything in a database.
        It also encodes timestamp so we can expire old sessions.
        """
        # The sessionid is data:timestamp:signature.
        # The signature is a hmac incorporating the appid and our secret key.
        # This both ties it to the application and prevents forgery.
        timestamp = hex(int(time.time()))
        # Remove hex-formatting guff e.g. "0x31220ead8L" => "31220ead8"
        timestamp = timestamp[2:]
        if timestamp.endswith("L"):
            timestamp = timestamp[:-1]
        # Append it to the data.
        # TODO: this will make userid visible in plaintext; encrypt it?
        data = "%s:%s" % (data, timestamp)
        # Append the signature.
        sigdata = data + "\x00" + appid
        sig = b64encode(hmac.new(self._sig_key, sigdata).digest())
        return "%s:%s" % (data, sig)

    def get_session_data(self, appid, sessionid):
        """Load the data associatd with the given session.

        In this implementation this involves validating the embedded signature,
        then just extracting the data from the sessionid itself.
        """
        try:
            (data, timestamp, sig) = sessionid.rsplit(":", 2)
        except ValueError:
            return None
        # Check for session expiry.
        try:
            expiry_time = int(timestamp, 16) + self.timeout
        except ValueError:
            return None
        if expiry_time <= time.time():
            return None
        # Check for valid signature.
        sigdata = "%s:%s\x00%s" % (data, timestamp, appid)
        expected_sig = b64encode(hmac.new(self._sig_key, sigdata).digest())
        if strings_differ(sig, expected_sig):
            return None
        # Hooray!
        return data


def HKDF_extract(salt, IKM):
    """HKDF-Extract; see RFC-2869 for the details."""
    return hmac.new(salt, IKM, hashlib.sha1).digest()


def HKDF_expand(PRK, info, L):
    """HKDF-Expand; see RFC-2869 for the details."""
    digest_size = hashlib.sha1().digest_size
    N = int(math.ceil(L * 1.0 / digest_size))
    assert N <= 255
    T = ""
    output = []
    for i in xrange(1, N+1):
        data = T + info + chr(i)
        T = hmac.new(PRK, data, hashlib.sha1).digest()
        output.append(T)
    return "".join(output)[:L]
