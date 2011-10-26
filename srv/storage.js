
var riak = require('riak-js');
var db = riak.getClient() // localhost at 8098?

// Data store layout:
// 'user' is an email address, verified by BrowserID, and serves as the primary 'bucket'.
// We use META to annonate an additional bucket, the audience.
// Keys and Values are application provided

function put(user, audience, key, value, cb) {
    db.save(
        encodeURIComponent(user),
        encodeURIComponent(key),
        value,
        {
            bucket: encodeURIComponent(audience),
            contentType: "application/json"
        },

        function(err) {
            cb(err);
        }
    );
}

function get(user, audience, key, cb) {
    db.get(
        encodeURIComponent(user),
        encodeURIComponent(key),

        function(err, data) {
            cb(err, data);
        }
    );
}

exports.put = put;
exports.get = get;
