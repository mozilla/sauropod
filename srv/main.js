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

var https = require('https');
var uuid = require('node-uuid');
var express = require('express');
var storage = require('./storage');
var log4js = require('log4js');
log4js.addAppender(log4js.consoleAppender());
log4js.addAppender(log4js.fileAppender('logs/sauropod.log'), 'sauropod');

var logger = log4js.getLogger('sauropod');

var sauropod = express.createServer(); // TODO: Transition to HTTPS server
sauropod.use(express.bodyParser());
sauropod.use(express.cookieParser());
sauropod.use(express.session({secret: 'apatosaurus'}));

// For testing only
sauropod.use(express.static(__dirname + '/'));

var tokens = {} // TODO: Randomly generated uuid's, only in memory

function verifyBrowserID(assertion, audience, cb)
{
    // Uncomment this to stub out verification for testing purposes
    //return cb({success: audience});
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
    verifyBrowserID(req.body.assertion, audience, function(id) {
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

logger.info('Serving on http://localhost:8001');
sauropod.listen(8001);
