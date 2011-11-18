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

// Globals ftw?
var user = false;
var token = false;
var audience = "http://localhost:8001";

function extractUser(assertion) {
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
        return window.atob(s); // Standard base64 decoder
    }

    var assert = JSON.parse(base64urldecode(assertion));
    var jwt = assert["certificates"][0];
    var data = jwt.split(".");
    var payload = JSON.parse(base64urldecode(data[1]));
    return payload["principal"]["email"];
}

function login() {
	navigator.id.getVerifiedEmail(function(assertion) {
		if (assertion) {
			document.getElementById("login").style.display = "none";
			setupSandbox(assertion);
		} else {
			document.getElementById("msg").innerHTML =
				"There was an error, please try logging in again: ";
		}
	})
}

function log(msg) {
	var box = document.getElementById("logbox");
	box.innerHTML = box.innerHTML + "<p>" + msg + "</p>";
}

function setupSandbox(assertion) {
	// Step 0 is to get an email out of the assertion. hmm.
	user = extractUser(assertion);
	log("We got an assertion for user " + user);

	// Step 1 is to create a session with Sauropod
	var req = new XMLHttpRequest();
	req.open('POST', '/session/start', false);
	req.onreadystatechange = function(evt) {
		if (req.readyState == 4) {
			if (req.status == 200) {
				var tok = req.responseText;
				log("Got a session token: " + tok);
				token = tok;

				// We can allow gets/puts npw
				document.getElementById("ops").style.display = "block";
			} else {
				log("There was an error: " + req.responseText);
			}
		}
	};

	var body = "assertion=" + assertion + "&audience=" + encodeURIComponent(audience);
	req.setRequestHeader("Content-Type", "application/x-www-form-urlencoded");
	req.send(body);
}

function doReq(type, key, val, cb) {
	var req = new XMLHttpRequest();
	var usr = encodeURIComponent(user);
	var appid = encodeURIComponent(audience);
	var key = encodeURIComponent(key);

	req.open(type, '/app/' + appid + '/users/' + usr + '/keys/' + key, false);
	req.onreadystatechange = function(evt) {
		if (req.readyState == 4) {
			if (req.status == 200) {
				var val = req.responseText;
				log("Got a " + type + " response: " + val);
				cb(val);
			} else {
				log("There was an error: " + req.responseText);
			}
		}
	};
	req.setRequestHeader("Signature", token);
	req.setRequestHeader("Content-Type", "application/x-www-form-urlencoded");

	if (val) {
		req.send("value=" + encodeURIComponent(val));
	} else {
		req.send(null);
	}
}

function doGet() {
	doReq("GET", document.getElementById("getKey").value, null, function(data) {
		var val = JSON.parse(data);
		document.getElementById("getValue").value = val.value;
	});
}

function doPut() {
	doReq("PUT", document.getElementById("putKey").value, document.getElementById("putValue").value, function() {

	});
}
