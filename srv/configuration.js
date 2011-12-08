const os = require('os');
const log4js = require('log4js');
log4js.addAppender(log4js.consoleAppender());
log4js.addAppender(log4js.fileAppender('logs/sauropod.log'), 'sauropod');

var config = {};

var dev = {};
try {
    dev = require('./dev-config').config;
    console.log('Using custom dev config module');
} catch (e) {
    dev = {
	serve: { listen: 8001 },
	storage: {
	    //hosts: ['appsync-hbase-stage1', 'appsync-hbase-stage2'],
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
	logger: undefined,
    };
}

var preview = {
    serve: { listen: 8001 },
    storage: {
	//hosts: ['appsync-hbase-stage1', 'appsync-hbase-stage2'],
	host: 'appsync-hbase-stage1',
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
    logger: undefined,
};

var table = {
    'dev': dev,
    'qa': {},
    'preview': preview,
    'prod': {}
};

var config = undefined;
var current = undefined;

exports.getConfig = function(which) {
    if (!which) {
	which = 'dev';
	console.log('Defaulting to dev config');
    }
    if (config === undefined || which != current) {
	current = which;
	config = table[which];
	if (config === undefined) {
	    console.log('Heyo!');
	}
	config.logger = log4js.getLogger('sauropod');
    }
    return config;
};

exports.getLogger = log4js.getLogger;
