/*
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
#   Anant Narayanan <anant@kix.in>
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
*/

const thrift = require('thrift');
const hbase = require('./gen-nodejs/Hbase');
const ttypes = require('./gen-nodejs/Hbase_types');
const crypto = require('crypto');
const config = require('./configuration').getConfig();
const genpool = require('generic-pool');

const NoSuchColumnFamily = new RegExp(/NoSuchColumnFamilyException/);

function hash(value) {
    // Use Skein insteaf of SHA-1?
    var sha = crypto.createHash('sha1');
    sha.update(value);
    return sha.digest('hex');
}

/* Data layout:
 *
 *  One table per "consumer" of sauropod, identified by the domain name
 *  of the application. This must match the "audience" in the BrowserID
 *  assertion issued.
 *
 *  One row per user. Hashed by hashUser(). We start out with one
 *  predefined column family "key:" and the actual key requested
 *  by the application is suffixed as a column qualifier.
 *
 * More discussion on:
 * https://groups.google.com/group/sauropod/browse_thread/thread/f4711de98ddabe3e
 */

function mogrify(err, audience) {
    /*
     * There are only three exceptions that the original HBase thrift server will raise:
     *
     * IOError  for any communication issues to the HBase cluster servers and as a general
     *          fallback for generic errors
     *
     * IllegalArgument  illegal or invalid argument
     *
     * AlreadyExists  a table with that name already exists
     */

    var http_err = {code: 400, message: 'Bad Request'};
    switch (err.name) {
    case 'IOError':
	if (err.message === audience) {
	    // Table doesn't exist, app not provisioned
	    http_err.code = 400;
	    http_err.message = 'application not provisioned';
	    // LOGME
	} else if (NoSuchColumnFamily.test(err.message)) {
	    http_err.code = 404;
	    http_err.message = "no such column family";
	    // LOGME
	} else {
	    http_err.code = 503;
	    http_err.message = 'Failed to communicate with HBase';
	    // LOGME
	}
	break;
    case 'IllegalArgument':
	http_err.message = 'invalid syntax: "'+err.message+'"';
	break;
    }

    return http_err;
}

/*
 * new_table doesn't use the connection pool since it's only ever called by the
 * stand along provisioning script
 */
function new_table(name, cfamilies, cb) {
    // Our client
    var timeout = config.storage.timeout > 0 ? config.storage.timeout : 1000;
    var conn = thrift.createConnection(next_host(), config.storage.port, timeout);
    var client = thrift.createClient(hbase, conn);

    var cfamily = new Array();
    for (var fam in cfamilies) {
	cfamily.push(new ttypes.ColumnDescriptor({name: cfamilies[fam]}));
    }

    client.createTable(name, cfamily, function(err) {
	cb(err, (err == 'AlreadyExists' ? true : false));
    });
}

function put(user, audience, key, value, cb) {
    pool.acquire(function(error, conn) {
        var cell = new ttypes.Mutation({column: "key:" + key, 'value': value });
        conn.client.mutateRow(hash(audience), hash(user), [cell], function(err, success) {
            pool.release(conn);
	    if (err) {
	        var http_err = mogrify(err, audience);
	        return cb(http_err);
	    }
	    // All's well
	    cb();
        });
    });
}

function get(user, audience, key, cb) {
    pool.acquire(function(error, conn) {
        conn.client.get(hash(audience), hash(user), "key:" + key, function(err, data) {
            pool.release(conn);
            if (err) {
	        var http_err = mogrify(err, audience);
	        return cb(err, success);
            } else {
                var data2 = data.shift() || { value: undefined, timestamp: -1 };
                data2.key = key;
                cb(err, data2);
            }
        });
    });
}

function ping(cb) {
    pool.acquire(function(error, conn) {
        conn.client.atomicIncrement(heart.table, heart.row, heart.column, 1,
			            function(err, success) {
                                        pool.release(conn);
			                cb(err);
			            });
    });
}

var host_idx = 0;
function next_host() {
    if (host_idx >= config.storage.hosts.length) {
        host_idx = 0;
    }
    var host = config.storage.hosts[host_idx];
    host_idx++;
    return host;
}

var pool = genpool.Pool({
    name: 'hbase-thrift',
    create:  function(callback) {
        var timeout = config.storage.timeout > 0 ? config.storage.timeout : 1000;
        var conn = thrift.createConnection(next_host(), config.storage.port, timeout);
        var client = thrift.createClient(hbase, conn);

        // You can access the client from the connection but can't access the
        // connection from the client.  Wtf?
        callback(null, conn)
    },
    destroy: function(conn) { conn.end(); },
    max: config.thrift.pool.max,
    idleTimeoutMillis: config.thrift.pool.idle_timeout,
    reapIntervalMillis: config.thrift.pool.reap_interval,
    log: config.thrift.pool.log
});

/*
 * Make sure the table we use for healthchecks is up
 */
var heart = config.thrift.heartbeat;
pool.acquire(function(error, conn) {
    conn.client.createTable(heart.table,
		            [new ttypes.ColumnDescriptor({name: heart.cfamily})],
		            function(err, data) {
                                pool.release(conn);
                                if (err.name === 'AlreadyExists') {
	                            return;
                                } else if (err.name === 'IOError') {
	                            console.log('Failed to create table "' +heart.table+'": ' + err.message);
                                }
                            });
});

exports.hash = hash;
exports.new_table = new_table;
exports.put = put;
exports.get = get;
exports.ping = ping;
