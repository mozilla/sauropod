/* Stub for "provisioning" a new consumer of Sauropod
 * Keys will probably need to be setup here, but for now
 * we only setup a new hbase table for the given argument
 */
var args = process.argv.splice(2);

if (args.length != 1) {
	console.log("Error: incorect argument");
	process.exit(1);
}

function hash(value) {
    // Use Skein insteaf of SHA-1?
    var crypto = require("crypto");
    var sha = crypto.createHash('sha1');
    sha.update(value);
    return sha.digest('hex');
}

var hbase = require("hbase");
var tName = hash(args[0]);
var newTable = hbase().getTable(tName);

newTable.create(
	'key', function(err, success) {
		console.log('Table created: ' + (success ? 'yes' : 'no'));
	}
);
