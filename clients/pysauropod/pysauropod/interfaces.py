# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.
"""

Interface definitions for the Sauropod data store.

"""

from zope.interface import Interface, Attribute


class ISauropodConnection(Interface):
    """Interface representing a top-level connection to a Sauropod data store.

    Objects implementing this interface encapsulate the high-level connection
    information for a Sauropod data store.  They can be used to obtain an
    ISauropodSession object through which data access can be performed.
    """

    appid = Attribute("String identifying the app that owns this connection")

    def close():
        """Close down the connection.

        This method releases any resources held by the connection and tears
        down the internal state.  You should not use a connection after it has
        been closed.
        """

    def start_session(userid, credentials, **kwds):
        """Start a data access session.

        This method starts a data access session as a particular user, using
        the given credentials to authenticate to the store.  The data available
        will depend on the permissions associated with those credentials.

        Any additional keyword arguments will be passed on to the created
        ISauropodSession object.
        """

    def resume_session(userid, sessionid, **kwds):
        """Resume a data access session.

        This method resumes the data access session identified by the given
        sessionid.  The data available will depend on the credentials used
        to authenticate when creating the session.

        Any additional keyword arguments will be passed on to the created
        ISauropodSession object.
        """


class ISauropodSession(Interface):
    """Interface to a per-user data access session.

    Objects implementing this interface encapsulate access to Sauropod data
    in the context of a specific user.  It allows you to get, put and delete
    keys by name, assuming that the user has appropriate permissions.
    """

    connection = Attribute("Reference to the owning ISauropodConnection")
    userid = Attribute("String identifying the user that owns this session")

    def close():
        """Close down the session.

        This method releases any resources held by the session and tears down
        the internal state.  You should not use a session after it has been
        closed.
        """

    def getitem(key, userid=None, appid=None):
        """Get the item stored under the specified key.

        This method takes the name of a key and retreives the Item stored
        there.  This allows you to retrieve the value along with any other
        metadata such as the etag.  If you just need to value, the get()
        method provides a simpler interface.

        By default this accesses the bucket for the owning userid and appid.
        Use the optional arguments "userid" and/or "appid" to override this
        (assuming, of course, that you have the appropriate permissions).
        """

    def get(key, userid=None, appid=None):
        """Get the value stored under the specified key.

        This method takes the name of a key and retreives the string value
        that is stored there.

        By default this accesses the bucket for the owning userid and appid.
        Use the optional arguments "userid" and/or "appid" to override this
        (assuming, of course, that you have the appropriate permissions).
        """

    def set(key, value, userid=None, appid=None, if_match=None):
        """Set the value stored under the specified key.

        This method takes the name of a key and a string value, and stores the
        value under the specified key.

        By default this accesses the bucket for the owning userid and appid.
        Use the optional arguments "userid" and/or "appid" to override this
        (assuming, of course, that you have the appropriate permissions).
        """

    def delete(key, userid=None, appid=None, if_match=None):
        """Delete the value stored under the specified key.

        This method takes the name of a key and deletes the value currently
        stored under that key.

        By default this accesses the bucket for the owning userid and appid.
        Use the optional arguments "userid" and/or "appid" to override this
        (assuming, of course, that you have the appropriate permissions).
        """


class ISauropodBackend(Interface):
    """Interface to backend storage for Sauropod.

    Objects implementing this interface encapsulate backend storage operations
    for sauropod.  They provide essentially the same operations as a session,
    but must be explicitly provided with the appid and userid.  They perform
    no authentication of the provided data (although they may still perform
    permission checking).
    """

    def close():
        """Close down the backend.

        This method releases any resources held by the backend and tears down
        the internal state.  You should not try to use a backend after it has
        been closed.
        """

    def getitem(appid, userid, key):
        """Get the item stored under the specified key.

        This method takes the name of a key and retreives the Item stored
        there.  This allows you to retrieve the value along with any other
        metadata such as the etag.
        """

    def set(appid, userid, key, value, if_match=None):
        """Set the value stored under the specified key.

        This method takes the name of a key and a string value, and stores the
        value under the specified key.
        """

    def delete(appid, userid, key, if_match=None):
        """Delete the value stored under the specified key.

        This method takes the name of a key and deletes the value currently
        stored under that key.
        """


class Item(object):
    """Individual item stored in Sauropod.

    Instances of Item represent an individual key/value item stored in
    Sauropod, along with all its metadata.  Interesting attributes are:

        * appid:    the application that this item belongs to
        * userid:   the user that this item belongs to
        * key:      the key under which this item is stored
        * value:    the value stored for this item
        * etag:     opaque etag to allow conflict detection

    """

    def __init__(self, appid, userid, key, value, etag):
        self.appid = appid
        self.userid = userid
        self.key = key
        self.value = value
        self.etag = etag
