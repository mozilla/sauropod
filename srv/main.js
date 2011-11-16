
var https = require('https');
var uuid = require('node-uuid');
var express = require('express');
var storage = require('./storage');

var sauropod = express.createServer(); // TODO: Transition to HTTPS server
sauropod.use(express.bodyParser());
sauropod.use(express.cookieParser());
sauropod.use(express.session({secret: 'apatosaurus'}));

// For testing only
sauropod.use(express.static(__dirname + '/'));

var tokens = {} // TODO: Randomly generated uuid's, only in memory

function verifyBrowserID(assertion, audience, cb)
{
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
        response.on('end', function () {
            var data = JSON.parse(allData);
            if (data.status != 'okay') {
                cb({'error': 'Invalid user'});
            } else {
                cb({'success': data.email});
            }
        });
    });

    verify.on('error', function(e) {
        console.log('Could not make verification request ' + e.message);
    });

    verify.write(cert);
    verify.end();
}

function verifySignature(sig) {
    // TODO: Signature is simply the token for now
    // TODO: How does :userid map to user in signature?
    for (var audience in tokens) {
        for (var email in tokens[audience]) {
            if (tokens[audience][email] == sig) {
                return {user: email, bucket: audience};
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

            var token = uuid();
            tokens[audience][email] = token;
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
                res.send("Error " + err, 500);
            }
        });
    }
});

console.log('Serving on http://localhost:8000');
sauropod.listen(8000);
