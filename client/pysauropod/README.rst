
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
under consideration.


Session Management
==================

All storage requests must be performed in the context of a **session**, which
identifies both the originating application and the active user.  Requests
are tied to a session by signing them with standard OAuth Authentication
headers.  In OAuth parlance this is two-legged authentication with:

  * consumer key =      application id
  * consumer secret =   application secret key
  * token =             session id
  * token secret =      session secret key

To begin a session, the application must make a signed POST request containing
valid user credentials.  We assume BrowserID credentials throughout::

    POST /session/start HTTP/1.1
    Host: v1.sauropod.mozilla.org
    Authorization: OAuth realm="Sauropod",
                         oauth_consumer_key="[APP-ID]",
                         oauth_timestamp="[TIMESTAMP]",
                         oauth_nonce="[RANDOM-NONCE]",
                         oauth_signature_method="HMAC-SHA1",
                         oauth_signature="[REQUEST-SIGNATURE]"

    assertion=[BROWSERID-ASSERTION]&audience=[APP-DOMAIN]

Sauropod will reply with an oauth token and secret to use for signing future
requests::

    HTTP/1.1 200 OK

    oauth_token=[SESSION-ID]&oauth_token_secret=[SESSION-SECRET-KEY]

If attempting access via an unrecognized, expired or invalid session token,
Sauropod will send a "401 Unauthorized" response.  Clients should start
a fresh session via the above technique.


Storage Operations
==================

An individual item of data in Sauropod is identified by its owning appid, its
owning userid, and its key.  This is exposed as a standard HTTP resource.
Create or update a key using PUT::

    PUT /app/[APP-ID]/users/[USER-ID]/keys/[KEY] HTTP/1.1
    Host: v1.sauropod.mozilla.org
    Authorization: OAuth realm="Sauropod" ...etc...

    [STORED-VALUE]

::

    HTTP/1.1 204 No Content
    ETag: "b7d645e6c03165bee2523a9a62a6d4e1"

Get the stored value using GET::

    GET /app/[APP-ID]/users/[USER-ID]/keys/[KEY] HTTP/1.1
    Host: v1.sauropod.mozilla.org
    Authorization: OAuth realm="Sauropod" ...etc...

::

    HTTP/1.1 200 OK
    ETag: "b7d645e6c03165bee2523a9a62a6d4e1"

    [STORED-VALUE]

Delete the key using DELETE::

    DELETE /app/[APP-ID]/users/[USER-ID]/keys/[KEY] HTTP/1.1
    Host: v1.sauropod.mozilla.org
    Authorization: OAuth realm="Sauropod" ...etc...

::

    HTTP/1.1 204 No Content

Note that Sauropod automatically assigns an etag to each key.  This can be
used to provide basic conflict-management using the standard If-Match and
If-None-Match headers.  Requests with a non-matching etag will fail::

    PUT /app/[APP-ID]/users/[USER-ID]/keys/[KEY] HTTP/1.1
    Host: v1.sauropod.mozilla.org
    Authorization: OAuth realm="Sauropod" ...etc...
    If-Match: "c6fd4dc2c2d8a356b19bb7d6e6b47cb1"

    [UPDATED-VALUE]

::

    HTTP/1.1 412 Precondition Failed
    ETag: "b7d645e6c03165bee2523a9a62a6d4e1"

While requests with a correctly matching etag will succeed::

    PUT /app/[APP-ID]/users/[USER-ID]/keys/[KEY] HTTP/1.1
    Host: v1.sauropod.mozilla.org
    Authorization: OAuth realm="Sauropod" ...etc...
    If-Match: "b7d645e6c03165bee2523a9a62a6d4e1"

    [UPDATED-VALUE]

::

    HTTP/1.1 204 No Content
    ETag: "1db61e70824066547de8990b32ebc660"


Listing Operations
==================

**NOTE**:  depending on the storage implementation, these lists may need to
be explicitly maintained and updated by a background process.  They should
not be considered real-time accurate.

The list of all keys in a particular bucket can be obtained via GET request
to the bucket URL::

    GET /app/[APP-ID]/users/[USER-ID]/keys/ HTTP/1.1
    Host: v1.sauropod.mozilla.org
    Authorization: OAuth realm="Sauropod" ...etc...

::

    HTTP/1.1 200 OK
    Content-Type: text/newlines

    key1
    my_second_key
    some_other_key

The keys are returned in sorted ascending order.  It is possible to restrict
the listing to keys within a certain range, by specifying "start" and/or "end"
in the query parameters::

    GET /app/[APP-ID]/users/[USER-ID]/keys/?start=my HTTP/1.1
    Host: v1.sauropod.mozilla.org
    Authorization: OAuth realm="Sauropod" ...etc...

::

    HTTP/1.1 200 OK
    Content-Type: text/newlines

    my_second_key
    some_other_key

It is also possible to restrict the number of keys returned in a single query,
by specifying "limit" in the query parameters::

    GET /app/[APP-ID]/users/[USER-ID]/keys/?limit=2 HTTP/1.1
    Host: v1.sauropod.mozilla.org
    Authorization: OAuth realm="Sauropod" ...etc...

::

    HTTP/1.1 200 OK
    Content-Type: text/newlines

    key1
    my_second_key

Combining these query parameters allows range queries and pagination to be
performed as required by the application.

A similar lising interface is available to find all the users with data
stored for a given application::

    GET /app/[APP-ID]/users/?limit=3 HTTP/1.1
    Host: v1.sauropod.mozilla.org
    Authorization: OAuth realm="Sauropod" ...etc...

::

    HTTP/1.1 200 OK
    Content-Type: text/newlines

    user1
    user2
    user3


And to find all the applications with data stored for a particular user::

    GET /user/[USER-ID]/apps/?limit=3 HTTP/1.1
    Host: v1.sauropod.mozilla.org
    Authorization: OAuth realm="Sauropod" ...etc...

::

    HTTP/1.1 200 OK
    Content-Type: text/newlines

    application1
    application2
    application3

Of course, the items that appear in these listings will depend on the access
permissions of the user and the application making the query.


Aggregation Operations
======================

Sauropod supports flexible queries and aggregation over the stored data by
means of the map/reduce paradigm.

**TODO**: how can we easily specify map/reduce jobs?  We can take ideas
from Riak, CouchDB, Apache Pig, ...?

To submit a map/reduce job for processing, POST to the top-level map/reduce
URL like so::

    POST /mapred/ HTTP/1.1
    Host: v1.sauropod.mozilla.org
    Authorization: OAuth realm="Sauropod" ...etc...

    [NOT-YET-DEFINED-JOB-DESCRIPTION-DATA]

::

    HTTP/1.1 201 Created
    Location: https://v1.sauropod.mozilla.org/mapred/jobs/[JOB-ID]

The job will be accepted for processing and the request will return without
waiting for it to complete.  To read data produced by the job, GET the job
URL provided by the server::

    GET /mapred/jobs/[JOB-ID] HTTP/1.1
    Host: v1.sauropod.mozilla.org
    Authorization: OAuth realm="Sauropod" ...etc...

::

    HTTP/1.1 200 OK
    Content-Type multipart/mixed; boundary="6528a7195e54496f4d8e2f571c7d177a"

    --6528a7195e54496f4d8e2f571c7d177a
    Content-Type: application/octet-stream

    [AN OUTPUT ITEM FROM THE MAP/REDUCE JOB]
    --6528a7195e54496f4d8e2f571c7d177a
    Content-Type: application/octet-stream

    [ANOTHER OUTPUT ITEM FROM THE MAP/REDUCE JOB]
    --6528a7195e54496f4d8e2f571c7d177a--

The response returned from this URL will be a multipart/mixed document
with each part containing a single item of output.  The parts are written
as they become available, allowing the client to stream partial results
from the server.

To perform more efficient jobs over restricted sets of data, you can also
start a map/reduce job tied to a specific application::

    POST /app/[APP-ID]/mapred/ HTTP/1.1
    Host: v1.sauropod.mozilla.org
    Authorization: OAuth realm="Sauropod" ...etc...

    [NOT-YET-DEFINED-JOB-DESCRIPTION-DATA]

::

    HTTP/1.1 201 Created
    Location: https://v1.sauropod.mozilla.org/mapred/jobs/[JOB-ID]

Or to a specific user::

    POST /user/[USER-ID]/mapred/ HTTP/1.1
    Host: v1.sauropod.mozilla.org
    Authorization: OAuth realm="Sauropod" ...etc...

    [NOT-YET-DEFINED-JOB-DESCRIPTION-DATA]

::

    HTTP/1.1 201 Created
    Location: https://v1.sauropod.mozilla.org/mapred/jobs/[JOB-ID]

Or even to a specific bucket::

    POST /app/[APP-ID]/users/[USER-ID]/mapred/ HTTP/1.1
    Host: v1.sauropod.mozilla.org
    Authorization: OAuth realm="Sauropod" ...etc...

    [NOT-YET-DEFINED-JOB-DESCRIPTION-DATA]

::

    HTTP/1.1 201 Created
    Location: https://v1.sauropod.mozilla.org/mapred/jobs/[JOB-ID]
