
==========================================
Sauropod:  a massive impervious data-store
==========================================

Sauropod is a key-value store.  It is designed for secure, scalable storage of
multi-tenanted data.  It supports millions of users and thousands of different
applications all accessing a single instance of the store, without trampling
on each other's data or each other's privacy.


Basic Concepts
==============

All storage operations in Sauropod are tied to a specific **application** and
a specific **user**, identified by an *appid* and a *userid* respectively.
The Sauropod server requires authentication from both the application and the
user before permitting any access to the store.

Each (appid, userid) pair identifies a **bucket**, which acts as an independent
set of key-value pairs.  The basic units of storage are **keys** inside each
bucket, which provide the standard get/put/delete operations.

You can think of the store as a three-level heirarchy mapping keys to values::

    appid / userid / key => value

Sauropod restricts data access based on fine-grained permissions, which can be
applied both to users and to applications.  It is possible to allow or deny
list, read and write access at the level of an individual key, a whole bucket,
or an entire application.

Sauropod also provides facilities for performing cross-bucket data queries,
e.g. aggregation over data belonging to all the users for a particular
application.  Such aggregation respects the permissions defined on each key
under consideration.  (And actually, they're not implemented yet).


API
===

To connect to a Sauropod store, use the "connect" function and pass in the
URL of the store and your application ID::

    >>> c = pysauropod.connect("http://localhost:8000", "SOMEAPP")


All storage requests must be performed in the context of a **session**, which
identifies both the originating application and the active user.  To start
a session you must provide a userid and a dict of credentials to authenticate
as that user::

    >>> credentials = showhow_get_browserid_assertion("user@example.com")
    >>> s = c.start_session("user@example.com", credentials)


The session object then acts like a simple key-value store where you can
get, set and delete values by key::

    >>> s.set("test", "TEST")
    >>> s.get("test")
    'TEST'
    >>> s.delete("test")
    >>> s.get("test")
    ...
    KeyError: 'test'

