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

var hbase = require('hbase');
var crypto = require('crypto');
var db = hbase({
    host: '127.0.0.1',
    port: 8080
});

db.getVersion(function(err, version) {
   console.log(version);
});

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

function put(user, audience, key, value, cb) {
    var row = db.getRow(hash(audience), hash(user));
    row.put("key:" + key, value, function(err, success) {
        cb(err);
    });
}

function get(user, audience, key, cb) {
    var row = db.getRow(hash(audience), hash(user));
    row.get("key:" + key, function(err, success) {
        var data = {};
        if (err) {
            cb(err, success);
        } else {
            data.key = key;
            data.value = success[0].$;
            data.timestamp = success[0].timestamp;
            cb(err, data);
        }
    });
}

exports.put = put;
exports.get = get;
