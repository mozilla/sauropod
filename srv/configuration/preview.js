module.exports = {
    storage: {
        //hosts: ['appsync-hbase-stage1', 'appsync-hbase-stage2'],
        host: 'appsync-hbase-stage1',
        port: 9090,
        backend: './storage-thrift',
    }
};
