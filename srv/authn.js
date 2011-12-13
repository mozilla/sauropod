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


//  Authentication routines for Sauropod.
//
//  All data access in Sauropod takes place in the context of a "session".
//  You start a session by sending some BrowserID credentials, and get back
//  a session token to include in subsequent requests.
//
//  Internally, session tokens are signed-and-encrypted blobs that include
//  the user and bucket, to avoid having to maintain state on the server.
//  They take the form ENCRYPT(timestamp:userid:bucket):SIGNATURE.

var https = require("https");
var crypto = require("crypto");
var url = require("url");

var config = require("./configuration").getConfig();
var logger = config.logger;

// Use the algorithms specified in the config.
//
var ENCRYPTION_ALGO = config.authn.encryption_algorithm || "aes192";
var HASH_ALGO = config.authn.hash_algorithm || "sha1";

var HASH_DIGEST_SIZE = (function() {
  var hmac = crypto.createHash(HASH_ALGO);
  return hmac.digest().length;
})()


// HKDF-Extract and HKDF-Expand, straight from RFC-5869.
// We use these for deriving keys below.
//
function HKDFExtract(salt, IKM) {
    var hmac = crypto.createHmac(HASH_ALGO, salt);
    hmac.update(IKM);
    return hmac.digest();
}

function HKDFExpand(PRK, info, L) {
    var N = Math.ceil(L / HASH_DIGEST_SIZE);
    if (N > 255) {
        throw "can't generate that much key:" + L;
    }
    var T = "";
    var output = [];
    for (var i=1; i<=N; i++) {
        var data = T + info + String.fromCharCode(i);
        var hmac = crypto.createHmac(HASH_ALGO, PRK);
        hmac.update(data);
        T = hmac.digest();
        output[output.length] = T;
    }
    return output.join("").substr(0, L);
}


//  Derive secret keys from the master secret in the config.
//  We use HKDF to make separate keys for each purpose, so that we don't
//  accidentally become e.g. a signature oracle.  Maybe not necessary
//  but it seems prudent.
//
SECRET_KEY = HKDFExtract("sauropod.authn", config.secret_key);
SIGNING_KEY = HKDFExpand(SECRET_KEY, "SIGNING", 16);
ENCRYPTION_KEY = HKDFExpand(SECRET_KEY, "ENCRYPTION", 16);


// Generate a new session token.
//
function makeSessionToken(user, bucket) {
    user = encodeURIComponent(user);
    bucket = encodeURIComponent(bucket);
    var now = new Date().getTime();
    var token = now + ":" + user + ":" + bucket;
    // Encrypt it for transmission to client.
    var crypter = crypto.createCipher(ENCRYPTION_ALGO, ENCRYPTION_KEY);
    token = crypter.update(token, "binary", "base64");
    token = token + crypter.final("base64");
    // Sign it with an HMAC.
    var signer = crypto.createHmac(HASH_ALGO, SIGNING_KEY);
    signer.update(token);
    token = token + ":" + signer.digest("base64");
    return token
}


//  Verify a session token.
//
function verifySessionToken(token) {
    var bits = token.split(":");
    if (bits.length != 2) {
        return false;
    }
    var data = bits[0];
    var sig = bits[1];
    //  Validate the signature with timing-invariant string compare.
    var signer = crypto.createHmac(HASH_ALGO, SIGNING_KEY);
    signer.update(data);
    var good_sig = signer.digest("base64");
    if(good_sig.length != sig.length) {
        return false;
    }
    var matches = true;
    for (var i=0; i<sig.length; i++) {
        matches = matches && (sig.charAt(i) == good_sig.charAt(i))
    }
    if (!matches) {
        return false;
    }
    //  Decrypt the embedded data.
    var crypter = crypto.createDecipher(ENCRYPTION_ALGO, ENCRYPTION_KEY);
    data = crypter.update(data, "base64", "binary");
    data = data + crypter.final("binary");
    bits = data.split(":");
    if (bits.length != 3) {
        return false;
    }
    //  TODO: expire the session based on embedded timestamp?
    return {
        user: decodeURIComponent(bits[1]),
        bucket: decodeURIComponent(bits[2])
    };
}


//  A dummy routine that just parses BrowserID assertions without verifying.
//  For use in testing scenarios.
//
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
        if(assertion.indexOf("~") != -1) {
            var bundle = assertion.split("~");
            var cert = bundle[bundle.length - 2];
            var assert = bundle[bundle.length - 1];
        } else {
            var bundle = JSON.parse(base64urldecode(assertion));
            var certs = bundle["certificates"];
            var cert = certs[certs.length - 1];
            var assert = bundle["assertion"];
        }
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
//
function verifyBrowserID(assertion, audience, cb) {
    var cert = 'assertion=' + encodeURIComponent(assertion) +
               '&audience=' + encodeURIComponent(audience);

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
                    logger.warn('Invalid BrowserID login: (reason) ' +
                                data.reason);
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

    //verify.connection.setTimeout(5000, function() {
    //    logger.error('Timeout on the response from BrowserID');
    //    cb({'error': 'BrowserID Timeout'});
    //    verify.abort();
    //});

    verify.on('error', function(e) {
        cb({'error': 'BrowserID Verification Failure'});
        logger.error('Could not make verification request ' + e.message);
    });

    verify.write(cert);
    verify.end();
}


//  Normalize an audience string.
//  This ensures that the audience is in the canonical form:
//
//    protocol://host:optional-port
//
var STANDARD_PORTS = {
  "http:": "80",
  "https:": "443"
}
function normalizeAudience(audience) {
   //  Note: url.parse() lowercases things for us, which is nice.
   var aud = url.parse(audience);
   //  Default to "https" as the protocol.
   var result = aud.protocol || "https:";
   //  If the protocol is missing, the hostname might be parsed as pathname.
   var hostname = aud.hostname;
   if (!hostname) {
       hostname = aud.pathname.split("/")[0];
   }
   result += "//" + hostname;
   //  Don't include the port number if it's standard.
   if(aud.port && aud.port != STANDARD_PORTS[aud.protocol]) {
       result += ":" + aud.port
   }
   return result;
}


//  Start a new data access session.
//  The caller must provide a hash of credentials containing BrowserID
//  "assertion" and "audience".  The callback will be called with the
//  session token.
//
module.exports.startSession = function(credentials, cb) {
    var assertion = credentials.assertion;
    if (!assertion) {
        return cb("Missing assertion");
    }
    var audience = credentials.audience;
    if (!audience) {
        return cb("Missing audience");
    }
    // Mock out verification if told by the config.
    var verifyFunc = verifyBrowserID;
    if (config.authn.mock) {
        verifyFunc = dummyVerifyBrowserID;
    }
    verifyFunc(assertion, audience, function(id) {
        if (!id.success) {
            return cb(id.error);
        }
        var email = id.success;
        var token = makeSessionToken(email, normalizeAudience(audience));
        cb(undefined, token);
    });
};


//  Verify an existing session token.
//  The callback will be called with a hash giving "user" and "bucket"
//  for the session.
//
module.exports.verify = function(token, cb) {
    var data = verifySessionToken(token);
    if (!data) {
        return cb("Invalid token");
    }
    cb(undefined, data);
};
