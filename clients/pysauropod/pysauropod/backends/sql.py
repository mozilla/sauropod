# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.
"""

SQLAlchemy-based backend for the Sauropod data store.

"""

import urlparse
from hashlib import md5

from zope.interface import implements

from sqlalchemy.pool import QueuePool
from sqlalchemy import (Integer, String, LargeBinary, Column, Index,
                        ForeignKeyConstraint, Table, MetaData, create_engine)

from pysauropod.errors import ConflictError
from pysauropod.interfaces import ISauropodBackend, Item


metadata = MetaData()
tables = []

# Table mapping (appid, userid) pairs to integer bucket ids.
#
buckets = Table("buckets", metadata,
    Column("bucket", Integer, primary_key=True, autoincrement=True),
    Column("appid",  String(64), nullable=False),
    Column("userid",  String(64), nullable=False),
)
Index("idx_buckets", buckets.c.appid, buckets.c.userid, unique=True)
tables.append(buckets)

# Table mapping (bucket, key) to value
#
items = Table("items", metadata,
    Column("bucket", Integer, primary_key=True, nullable=False),
    Column("key", String(256), primary_key=True, nullable=False),
    Column("value", LargeBinary, nullable=False),
    ForeignKeyConstraint(["bucket"], ["buckets.bucket"], ondelete="CASCADE"),
)
tables.append(items)


class SQLBackend(object):
    """ISauropodBackend implemented on top of an SQL database."""

    implements(ISauropodBackend)

    def __init__(self, sqluri, pool_size=100, pool_recycle=60,
                 reset_on_return=True, create_tables=False,
                 pool_max_overflow=10, no_pool=False,
                 pool_timeout=30, **kwds):
        self.sqluri = sqluri
        self.driver = urlparse.urlparse(sqluri).scheme
        # Create the engine pased on database type and given parameters.
        # SQLite :memory: engines are limited to a single shared connection,
        # while other SQLite engines get only the default pool options.
        if no_pool or self.driver == 'sqlite':
            sqlkw = {}
            if ":memory:" in sqluri or sqluri == "sqlite://":
                sqlkw['poolclass'] = QueuePool
                sqlkw['pool_size'] = 1
                sqlkw['max_overflow'] = 0
                sqlkw['connect_args'] = {'check_same_thread': False}
        else:
            sqlkw = {'pool_size': int(pool_size),
                     'pool_recycle': int(pool_recycle),
                     'pool_timeout': int(pool_timeout),
                     'max_overflow': int(pool_max_overflow)}
            if self.driver.startswith("mysql") or self.driver == "pymsql":
                sqlkw['reset_on_return'] = reset_on_return
        sqlkw['logging_name'] = 'sqlstore'
        self._engine = create_engine(sqluri, **sqlkw)
        # Bind the tables to the engine, creating if necessary.
        for table in tables:
            table.metadata.bind = self._engine
            if create_tables:
                table.create(checkfirst=True)
        self.engine_name = self._engine.name

    def close(self):
        """Close down the store."""
        self._engine.dispose()

    def execute(self, query, *args, **kwds):
        return self._engine.execute(query, *args, **kwds)

    def _getbucket(self, appid, userid):
        """Get the ID for the given bucket, creating if necessary."""
        get_query = "SELECT bucket FROM buckets"\
                    " WHERE appid = :appid AND userid = :userid"
        qargs = {"appid": appid, "userid": userid}
        row = self.execute(get_query, **qargs).fetchone()
        if row is None:
            ins_query = "INSERT INTO buckets VALUES (NULL, :appid, :userid)"
            try:
                self.execute(ins_query, **qargs)
            except Exception:
                # Someone already created it for us.
                # XXX: restrict to sqlalchemy conflict error
                pass
            row = self.execute(get_query, **qargs).fetchone()
        return row[0]

    def getitem(self, appid, userid, key, connection=None):
        """Get the item stored under the specified key."""
        if connection is None:
            connection = self
        query = "SELECT i.value, k.bucket FROM items i, buckets k"\
                " WHERE i.bucket = k.bucket"\
                " AND k.appid = :appid AND k.userid = :userid"\
                " AND key = :key"
        qargs = {"appid": appid, "userid": userid, "key": key}
        row = connection.execute(query, **qargs).fetchone()
        if row is None:
            raise KeyError(key)
        etag = md5(row[0]).hexdigest()
        item = Item(appid, userid, key, row[0], etag)
        item.bucket = row[1]
        if isinstance(item.key, unicode):
            item.key = item.key.encode("utf8")
        if isinstance(item.value, unicode):
            item.value = item.value.encode("utf8")
        return item

    def set(self, appid, userid, key, value, if_match=None):
        """Set the value stored under the specified key."""
        qargs = {"key": key, "value": value}
        set_query = "UPDATE items SET value = :value"\
                    " WHERE bucket = :bucket AND key = :key"
        ins_query = "INSERT INTO items VALUES (:bucket, :key, :value)"
        # We need a transaction in order to check the etag.
        connection = self._engine.connect()
        trn = connection.begin()
        try:
            try:
                item = self.getitem(appid, userid, key, connection)
            except KeyError:
                if if_match is not None:
                    if if_match != "":
                        raise ConflictError(key)
                qargs["bucket"] = self._getbucket(appid, userid)
                connection.execute(ins_query, **qargs)
            else:
                if if_match is not None:
                    if item.etag != if_match:
                        raise ConflictError(key)
                qargs["bucket"] = item.bucket
                connection.execute(set_query, **qargs)
            trn.commit()
            etag = md5(value).hexdigest()
            return Item(appid, userid, key, value, etag)
        except:
            trn.rollback()
            raise
        finally:
            connection.close()

    def delete(self, appid, userid, key, if_match=None):
        """Delete the value stored under the specified key."""
        # We need a transaction in order to check the etag.
        # If etags were stored in the database we could do a "DELETE ... WHERE"
        # and then check the number of rows deleted.
        connection = self._engine.connect()
        trn = connection.begin()
        try:
            try:
                item = self.getitem(appid, userid, key, connection)
            except KeyError:
                if if_match is not None:
                    if if_match != "":
                        raise ConflictError(key)
                raise KeyError(key)
            else:
                if if_match is not None:
                    if item.etag != if_match:
                        raise ConflictError(key)
                qargs = {"bucket": item.bucket, "key": key}
                del_query = "DELETE FROM items"\
                            " WHERE bucket = :bucket AND key = :key"
                res = connection.execute(del_query, **qargs)
                # Check that we actualy deleted something
                if res.rowcount == 0:
                    raise KeyError(key)
            trn.commit()
        except:
            trn.rollback()
            raise
        finally:
            connection.close()

    def listkeys(self, appid, userid, start=None, end=None, limit=None):
        """List the keys available in the store."""
        qargs = {"appid": appid, "userid": userid,
                 "start": start, "end": end, "limit": limit}
        list_query = "SELECT i.key FROM items i, buckets k"\
                     " WHERE i.bucket = k.bucket"\
                     " AND k.appid = :appid AND k.userid = :userid"
        if start is not None:
            list_query += " AND i.key >= :start"
        if end is not None:
            list_query += " AND i.key < :end"
        list_query += " ORDER BY i.key ASC"
        if limit is not None:
            list_query += " LIMIT :limit"
        for row in self.execute(list_query, **qargs):
            if isinstance(row[0], unicode):
                yield row[0].encode("utf8")
            else:
                yield row[0]
