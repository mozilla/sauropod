
This directory contains FunkLoad load tests for the Sauropod web API.
See here for more details on FunkLoad:

    http://funkload.nuxeo.org/

To successfully run the loadtest, you will need to provision a Sauropod table
for the audience "http://sauropod.mozillalabs.com"::

    node provision.js http://sauropod.mozillalabs.com

Run Sauropod on localhost port 8001 in mock mode::

    node main.js mock

Then you can run through the full loadtest suite by doing::

    python test_sauropod.py

This will execute the tests and write reports into the "html" directory.
