
var riak = require('riak-js');
var express = require('express');

var db = riak.getClient() // localhost at 8098?

var sauropod = express.createServer(); // Transition to HTTPS server
sauropod.use(express.bodyParser());
sauropod.use(express.cookieParser());
sauropod.use(express.session({secret: 'apatosaurus'}));

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
        response.setEncoding('utf8');
        var allData = '';
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
	
});

