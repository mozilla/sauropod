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

Storage-related code for the minimal sauropod server.

"""

from collections import defaultdict

from zope.interface import implements, Interface


class IStorageDB(Interface):
    """Interface for implementing storage in Sauropod."""

    def get(appid, userid, key):
        """Get a key."""

    def set(appid, userid, key, value):
        """Set a key."""

    def delete(appid, userid, key):
        """Delete a key."""

    def listkeys(appid, userid, prefix=None):
        """List keys."""


class MemoryStorageDB(object):
    """In-memory storage for sauropod server."""
    implements(IStorageDB)

    def __init__(self):
        self.keyspaces = defaultdict(dict)

    def get(self, appid, userid, key):
        return self.keyspaces[(appid, userid)][key]

    def set(self, appid, userid, key, value):
        self.keyspaces[(appid, userid)][key] = value

    def delete(self, appid, userid, key):
        del self.keyspaces[(appid, userid)][key]

    def listkeys(self, appid, userid, prefix=None):
        for key in self.keyspaces[(appid, userid)]:
            if prefix is None or key.startswith(prefix):
                yield key

def includeme(config):
    storage = MemoryStorageDB()
    def register():
        config.registry.registerUtility(storage, IStorageDB)
    config.action(IStorageDB, register)
