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
# Portions created by the Initial Developer are Copyright (C) 2011
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

Helper functions for Sauropod

"""

import json
import urllib


BROWSERID_VERIFY_URL = 'https://browserid.org/verify'


def strings_differ(string1, string2):
    """Check whether two strings differ while avoiding timing attacks.

    This function returns True if the given strings differ and False
    if they are equal.  It's careful not to leak information about *where*
    they differ as a result of its running time, which can be very important
    to avoid certain timing-related crypto attacks:

        http://seb.dbzteam.org/crypto/python-oauth-timing-hmac.pdf

    """
    if len(string1) != len(string2):
        return True
    invalid_bits = 0
    for a, b in zip(string1, string2):
        invalid_bits += a != b
    return invalid_bits != 0


def verify_browserid(assertion, audience):
    """Verify the given BrowserID assertion.

    This function verifies the given BrowserID assertion.  If valid it
    returns a tuple (email, result). giving the asserted email address and 
    the JSON response from the verifier.  If invalid is returns a tuple
    (None, result) givig the JSON error data from the verifier.

    Currently this function just POSTs to the browserid.org verifier service.

    WARNING: this does no HTTPS certificate checking and so is completely open
             to credential forgery.  I'll fix that eventually...

    """
    # FIXME: check the TLS certificates.
    post_data = {"assertion": assertion, "audience": audience}
    post_data = urllib.urlencode(post_data)
    try:
        resp = urllib.urlopen(BROWSERID_VERIFY_URL, post_data)
        content_length = resp.info().get("Content-Length")
        if content_length is None:
            data = resp.read()
        else:
            data = resp.read(int(content_length))
        data = json.loads(data)
    except (ValueError, IOError):
        return None, {"status": "failure", "error": "BrowserID server error"}
    if resp.getcode() != 200:
        return None, data
    if data.get("status") != "okay":
        return None, data
    if data.get("audience") != audience:
        return None, data
    return data.get("email"), data


def dummy_verify_browserid(assertion, audience):
    """Verify the given Dummy BrowserID assertion.

    This function can be used to replace verify_browserid() for testing
    purposes.  Instead of a BrowserID assertion it accepts an email as a
    string, and returns that string unchanged as the asserted identity.

    If the given assertion doesn't look like an email address, or if the
    given audience is False, then an error response is returned.
    """
    if not assertion or "@" not in assertion:
        return None, {"status": "failure", "error": "invalid assertion"}
    if not audience:
        return None, {"status": "failure", "error": "invalid audience"}
    data = {}
    data["status"] = "okay"
    data["email"] = assertion
    data["audience"] = audience
    return assertion, data

