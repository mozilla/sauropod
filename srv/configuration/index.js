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
#   Ryan Kelly <rkelly@mozilla.com>
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

//  Configuration loader for Sauropod.
//  This module lets you load a named config like "dev" or "prod" by
//  doing:
//
//    var config = configuration.getConfig("dev");
//
//  Behind the scenes, this loads the module "configuration/dev.js",
//  merged it with some default configuration options, and returns the
//  resulting object.

const os = require('os');
const log4js = require('log4js');
log4js.addAppender(log4js.consoleAppender());
log4js.addAppender(log4js.fileAppender('logs/sauropod.log'), 'sauropod');


// Like $.extend from jQuery, but recursive.
// This is useful for deep cloning properties from multiple objects.
// We use it to merge config files with the default settings.
//
function deep_extend() {
    //  The first argument is the object to extend.
    //  It gets extended by the properties of all other arguments in turn.
    var obj = arguments[0];
    for (var i=1; i<arguments.length; i++) {
        var extra = arguments[i];
        for (var k in extra) {
            if (extra.hasOwnProperty(k)) {
                var vObj = obj[k];
                var vExtra = extra[k];
                //  If it's a non-object, overwrite on obj.
                //  If it's an object, maybe try a recursive clone.
                if (typeof vObj !== "object" || typeof vExtra !== "object") {
                    obj[k] = vExtra;
                } else {
                    deep_extend(vObj, vExtra);
                }
            }
        }
    }
    return obj;
}


// Default configuration options.
// These are basically the default dev configuration.
// 
var defaults = {
    secret_key: "apatosaurus",
    serve: {
        listen: 8001
    },
    authn: {
        mock: false
    },
    storage: {
        host: 'localhost',
        port: 9090,
        backend: './storage-thrift',
    },
    thrift: {
        heartbeat: {
            table: '__heartbeat__',
            cfamily: 'incr',
            row: os.hostname(),
            column: 'incr:a'
        },
    },
};


//  Holds the currently-selected config.
//  This is what you'll get if you call getConfig() with no arguments.
var config = undefined;
var current = undefined;


//  Get [and set] the active config.
//
var IS_ALPHANUM = /^[a-zA-Z0-9]+$/;
exports.getConfig = function(which) {
    // With no arguments, use the currently-active config.
    // If none is active, default to the dev config.
    if (!which) {
        if (typeof current !== "undefined") {
            return config;
        }
	which = 'dev';
	console.log('Defaulting to dev config');
    }
    // Santity-check the name, since we're going to require() it.
    if (!IS_ALPHANUM.test(which)) {
        throw "invalid config name: " + which;
    }
    // Load the name config, extending the defaults.
    // Store a reference to it for returning in subsequent calls.
    if (config === undefined || which != current) {
	current = which;
	config = deep_extend({}, defaults, require("./"+which));
	config.logger = log4js.getLogger('sauropod');
    }
    return config;
};

exports.getLogger = log4js.getLogger;
