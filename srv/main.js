
var riak = require('riak-js');
var uuid = require('node-uuid');
var express = require('express');

var db = riak.getClient() // localhost at 8098?

var sauropod = express.createServer(); // TODO: Transition to HTTPS server
sauropod.use(express.bodyParser());
sauropod.use(express.cookieParser());
sauropod.use(express.session({secret: 'apatosaurus'}));

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

sauropod.post('/session/start', function(req, res) {
    var audience = req.body.audience;
    verifyBrowserID(req.body.assertion, audience, function(id) {
        if ('success' in id) {
            var email = id['success'];
            if (!(audience in tokens)) {
                token[audience] = {};
            }
            tokens[audience][email] = uuid();
            res.send(tokens[audience][email]);
        } else {
            res.send(id.error, 401);
        }
    });
});

sauropod.put('/app/:appid/users/:userid/keys/:key', function(req, res) {
    // TODO: Signature is simply the token for now
    var signature = req.header('Signature');
    for (var )
    res.send("TBD", 501);
});

sauropod.get('/app/:appid/users/:userid/keys/:key', function(req, res) {
    res.send("TBD", 501);
});
