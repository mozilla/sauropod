
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
