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

// Command line argument specifies the configuration to load.
var conf = 'prod';
var args = process.argv.splice(2);
if (args.length >= 1) {
    conf = args[0];
}

var https = require('https');
var express = require('express');

var log4js = require('log4js');
var url = require('url');
log4js.addAppender(log4js.consoleAppender());
log4js.addAppender(log4js.fileAppender('logs/sauropod.log'), 'sauropod');

var connect = require('connect');
var config = require('./configuration').getConfig(conf);
var logger = config.logger;

console.log('Using the "' + config.storage.backend + '" storage backend');
var storage = require(config.storage.backend);
var authn = require("./authn");

var sauropod = express.createServer(); // TODO: Transition to HTTPS server
sauropod.use(connect.logger('short'));
sauropod.use(express.bodyParser());
sauropod.use(express.cookieParser());
sauropod.use(express.session({secret: 'apatosaurus'}));

// For testing only
sauropod.use(express.static(__dirname + '/'));

sauropod.post('/session/start', function(req, res) {
    authn.startSession(req.body, function(err, token) {
        if (err) {
            res.send(err, 401);
        } else {
            res.send(token);
        }
    });
});

sauropod.put('/app/:appid/users/:userid/keys/:key', function(req, res) {
    var key = req.params.key;
    var sig = req.header('Signature');
    authn.verify(sig, function(err, data) {
        if (err) {
            res.send("Invalid Signature", 401);
        } else {
            var user = data["user"];
            var bucket = data["bucket"];
            if (req.params.appid != bucket || req.params.userid != user) {
                res.send("Permission Denied", 403);
            } else {
                storage.put(user, bucket, key, req.body.value, function(err) {
                    if (err) {
                        res.send("Error " + err, 500);
                    } else {
                        res.send("OK", 200);
                    }
                });
            }
        }
    });
});

sauropod.get('/app/:appid/users/:userid/keys/:key', function(req, res) {
    var key = req.params.key;
    var sig = req.header('Signature');
    authn.verify(sig, function(err, session) {
        if (err) {
            res.send("Invalid Signature", 401);
        } else {
            var user = session["user"];
            var bucket = session["bucket"];
            if (req.params.appid != bucket || req.params.userid != user) {
                res.send("Permission Denied", 403);
            } else {
                storage.get(user, bucket, key, function(err, data) {
                    if (err) {
                        if (404 == err.code ) {
                            res.send('Not found', 404);
                        } else {
                            res.send("Error " + err, 500);
                            logger.error('storage.get failure "' + err +
                                         '" for ' + user + ' / ' + bucket + 
                                         ' / ' + key + ': ' +
                                         JSON.stringify(err));
                        }
                    } else {
                        console.log(data);
                        data.user = user;
                        data.bucket = bucket;
                        res.send(JSON.stringify(data), 200);
                    }
                });
            }
        }
    });
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
