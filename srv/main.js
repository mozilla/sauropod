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

// Command line argument specifies if to run with production
// browserID or mock verification
var verifyFunc = verifyBrowserID;
var conf = 'prod';
var args = process.argv.splice(2);
if (args.length >= 1) {
    if (args[0] == "mock") {
	verifyFunc = dummyVerifyBrowserID;
	conf = args[1];
    } else {
	conf = args[0];
    }
}

var https = require('https');
var uuid = require('node-uuid');
var express = require('express');
var connect = require('connect');
var config = require('./configuration').getConfig(conf);
var logger = config.logger;

console.log('Using the "' + config.storage.backend + '" storage backend');
var storage = require(config.storage.backend);


var sauropod = express.createServer(); // TODO: Transition to HTTPS server
sauropod.use(connect.logger('short'));
sauropod.use(express.bodyParser());
sauropod.use(express.cookieParser());
sauropod.use(express.session({secret: 'apatosaurus'}));

// For testing only
sauropod.use(express.static(__dirname + '/'));

var tokens = {} // TODO: Randomly generated uuid's, only in memory


//  A dummy routine that just parses BrowserID assertions without verifying.
//  For use in testing scenarios..
function dummyVerifyBrowserID(assertion, audience, cb) {
    function base64urldecode(arg) {
        var s = arg;
        s = s.replace(/-/g, '+'); // 62nd char of encoding
        s = s.replace(/_/g, '/'); // 63rd char of encoding
        switch (s.length % 4) // Pad with trailing '='s
        {
            case 0: break; // No pad chars in this case
            case 2: s += "=="; break; // Two pad chars
            case 3: s += "="; break; // One pad char
            default: throw new InputException("Illegal base64url string!");
        }
        var buf = new Buffer(s, "base64");
        return buf.toString("ascii");
    }
    function parseJWT(arg) {
        var data = arg.split(".");
        var payload = JSON.parse(base64urldecode(data[1]));
        return payload;
    }
    try {
        var bundle = JSON.parse(base64urldecode(assertion));
        var cert = bundle["certificates"][bundle["certificates"].length - 1];
        var assert = bundle["assertion"];
        if (parseJWT(assert)["aud"] != audience) {
            cb({'error': 'Invalid user'});
        } else {
            cb({'success': parseJWT(cert)["principal"]["email"]});
        }
    } catch (e) {
        cb({'error': 'Invalid assertion'});
    }
}


//  The real routine to verify BrowserID assertions.
//  For use in production.
function verifyBrowserID(assertion, audience, cb) {
    var cert = 'assertion=' + encodeURIComponent(assertion) + '&audience=' + encodeURIComponent(audience);

    var options = {
        host: 'browserid.org',
        path: '/verify',
        method: 'POST',
        headers: {
            'content-type': 'application/x-www-form-urlencoded',
            'content-length': '' + cert.length
        }
    };

    var verify = https.request(options, function(response) {
        var allData = '';
        response.setEncoding('utf8');
        response.on('data', function(chunk) {
            allData += chunk;
        });
        response.on('end', function() {
            try {
                var data = JSON.parse(allData);
                if (data.status != 'okay') {
                    logger.warn('Invalid BrowserID login: (reason) ' + data.reason);
                    cb({'error': 'Invalid user'});
                } else {
                    cb({'success': data.email});
                }
            } catch (e) {
                logger.error('Exception ' + e);
                cb({'error': 'Invalid user'});
            }

        });
    });

    /*
    verify.connection.setTimeout(5000, function() {
			logger.error('Timeout on the response from BrowserID');
      cb({'error': 'BrowserID Timeout'});
      verify.abort();
    });
    */

    verify.on('error', function(e) {
        cb({'error': 'BrowserID Verification Failure'});
        logger.error('Could not make verification request ' + e.message);
    });

    verify.write(cert);
    verify.end();
}

function verifySignature(sig) {
    // TODO: Signature is simply the token for now
    // TODO: How does :userid map to user in signature?
    // FIXME: 4 nested loops? This won't do at all.
    for (var audience in tokens) {
        for (var email in tokens[audience]) {
            var cTokens = tokens[audience][email];
            for (var i = 0; i < cTokens.length; i++) {
                if (cTokens[i] == sig) {
                    return {user: email, bucket: audience};
                }
            }
        }
    }

    return null;
}

sauropod.post('/session/start', function(req, res) {
    var audience = req.body.audience;
    verifyFunc(req.body.assertion, audience, function(id) {
        if ('success' in id) {
            var email = id['success'];
            if (!(audience in tokens)) {
                tokens[audience] = {};
            }

            /* You can have more than one session per user */
            if (!(email in tokens[audience])) {
                tokens[audience][email] = [];
            }

            var token = uuid();
            tokens[audience][email].push(token);
            res.send(token);
        } else {
            res.send(id.error, 401);
        }
    });
});

sauropod.put('/app/:appid/users/:userid/keys/:key', function(req, res) {
    var key = req.params.key;
    var sig = req.header('Signature');
    var verify = verifySignature(sig);

    if (!verify) {
        res.send("Invalid Signature", 401);
    } else {
        storage.put(verify["user"], verify["bucket"], key, req.body.value, function(err) {
            if (!err) {
                res.send("OK", 200);
            } else {
                res.send("Error " + err, 500);
            }
        });
    }
});

sauropod.get('/app/:appid/users/:userid/keys/:key', function(req, res) {
    var key = req.params.key;
    var sig = req.header('Signature');
    var verify = verifySignature(sig);

    if (!verify) {
        res.send("Invalid Signature", 401);
    } else {
        storage.get(verify["user"], verify["bucket"], key, function(err, data) {
            if (!err) {
                data.user = verify["user"];
                data.bucket = verify["bucket"];
                res.send(JSON.stringify(data), 200);
            } else {
                if (404 == err.code ) {
                    res.send('Not found', 404);
                }
                else {
                    res.send("Error " + err, 500);
                    // Log it
                    logger.error('storage.get failure "' + err + '" for ' + key + ': ' + JSON.stringify(err));
                }
            }
        });
    }
});

sauropod.get('/__heartbeat__', function(req, res) {
    storage.ping(function(err) {
        if(!err) {
            res.send("OK", 200);
        } else {
            res.send("ERROR: storage is not accessible", 500);
        }
    });
});

logger.info('Serving on http://localhost:8001');
sauropod.listen(config.serve.listen);
