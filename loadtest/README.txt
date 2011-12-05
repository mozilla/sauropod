
This directory contains FunkLoad load tests for the Sauropod web API.
See here for more details on FunkLoad:

    http://funkload.nuxeo.org/

To successfully run the tests, you will need to provision a Sauropod table
for the audience "http://sauropod.mozillalabs.com"::

    node provision.js http://sauropod.mozillalabs.com

Then disable assertion checking for sessions, and run Sauropod on localhost
port 8001 for use by the tests::

    node main.js

Confirm that your setup is working by running a single instance of the test
suite::

    fl-run-test test_simple.py

Then you can run the loadtest by doing::

    fl-run-bench test_simple.py SimpleTest.test_write_and_read_keys
 
And generate some pretty graphs with::

    fl-build-report --html --output-directory=html simple-bench.xml
