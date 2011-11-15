/* Stub for "provisioning" a new consumer of Sauropod
 * Keys will probably need to be setup here, but for now
 * we only setup a new hbase table for the given argument
 */
var args = process.argv.splice(2);

if (args.length != 1) {
	console.log("Error: incorect argument");
	process.exit(1);
}

var hbase = require("hbase");
var newTable = hbase.getTable(client, args[0]);

newTable.create(
	'key', function(err, success) {
		console.log('Table created: ' + (success ? 'yes' : 'no'));
	}
);
