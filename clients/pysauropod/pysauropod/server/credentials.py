# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.
"""

Credential-checking code for the minimal sauropod server.

"""

from zope.interface import implements, Interface

from mozsvc import plugin
from mozsvc.util import maybe_resolve_name

import vep


def includeme(config):
    """Include the default credential-checking definitions.

    Call this function on a pyramid configurator to register a utility for
    the ICredentialChecker interface.  The particular implementation to use
    will  be taken from the configurator settings dict, falling back to a
    BrowserID-based scheme as the default.
    """
    settings = config.get_settings()
    if "sauropod.credentials.backend" not in settings:
        default_backend = "pysauropod.server.credentials.BrowserIDCredentials"
        settings["sauropod.credentials.backend"] = default_backend
        settings["sauropod.credentials.verifier"] = "vep:DummyVerifier"
    plugin.load_and_register("sauropod.credentials", config)


class ICredentialsManager(Interface):
    """Interface for implementing credentials-checking."""

    def check_credentials(credentials):
        """Check the given credentials.

        This method checks the given dict of credentials.  If valid then it
        returns an (appid, userid) tuple; if invalid then it returns a tuple
        of two Nones.
        """


class BrowserIDCredentials(object):
    """Credentials-checking based on BrowserID.

    This class implements the ICredentialsManager interface using browserid
    assertions as the credentials.  The appid is the assertion audience, the
    userid is the asserted email address.
    """
    implements(ICredentialsManager)

    def __init__(self, verifier=None):
        if verifier is None:
            verifier = "vep:RemoteVerifier"
        verifier = maybe_resolve_name(verifier)
        if callable(verifier):
            verifier = verifier()
        self._verifier = verifier

    def check_credentials(self, credentials):
        assertion = credentials.get("assertion")
        audience = credentials.get("audience")
        if assertion is None or audience is None:
            return (None, None)
        try:
            email = self._verifier.verify(assertion, audience)["email"]
        except (ValueError, vep.TrustError):
            return (None, None)
        return (audience, email)
