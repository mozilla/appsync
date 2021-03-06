App Sync
========

This implements the `Open Web
Application <https://apps.mozillalabs.com>`_ synchronization protocol.
The client is implemented in `the main openwebapps
repository <https://github.com/mozilla/openwebapps>`_.

Testing
-------

To run the server in a configuration that is fairly equivalent to the
https://myapps.mozillalabs.com setup, use::

    $ git clone https://github.com/mozilla/openwebapps.git
    $ export OPENWEBAPPS=$(pwd)/openwebapps
    $ git clone https://github.com/mozilla/apps.mozillalabs.com.git
    $ export APPS=$(pwd)/apps.mozillalabs.com
    $ git clone https://github.com/mozilla/appsync.git
    $ cd appsync
    $ pip -E test-env install -r prod-reqs.txt
    $ ./test-env/bin/paster serve etc/appsync-dev.ini -n myapps --reload

Now you can load ``http://localhost:5000/`` to get the dashboard, and
to get some apps to install go to
``http://localhost:5000/apps/appdir/``

You may want to change ``[storage]`` in ``etc/appsync-dev.ini`` to use
a SQLite database (there are comments in that file to show how).

Benching
--------

To perform a stress test on the server, install Funkload::

    $ pip -E test-env install Funkload


Then run the Appsync server::

    $ ./test-env/bin/paster serve etc/appsync-dev.ini --daemon


And verify the server is properly set by running a single test::

    $ make loadonce
    cd loadtest; ../bin/fl-run-test simple.py
    .
    -----------------------------------------------------
    Ran 1 test in 2.742s

    OK


You can now run a full stress test::

    $ make load
    Benching
    ========

    * setUpBench hook: ... done.

    Cycle #0 with 5 virtual users
    -----------------------------

    * setUpCycle hook: ... done.
    * Current time: 2011-12-05T14:47:14.737983
    * Starting threads: ..... done.
    * Logging for 30s (until 2011-12-05T14:47:44.796607): ........
    ...


You can configure the load test with a few options:

- **HOST**: the AppSync Server the test is run against
  (default: http://localhost:5000)

- **DURATION**: the duration of a cycle in seconds
  (default: 30)

- **CYCLES**: cycles to run. Number of virtual users to run
  per cycle, separated by columns. (default: 5:10:20)

Let's run 50, 100, then 200 users for a duration of 1 minute on the
myapps.example.com ::

    $ make load HOST=http://myapps.example.com DURATION=60 CYCLES=50:100:200


Setting up the Backoff header in Memcache
-----------------------------------------

To slow down the clients requests, you can set up a special value in Memcache
that will add a *X-Sync-Poll* header to all GETs' responses.

The **appsync-backoff** script is provided for this::


    $ appsync-backoff get
    The Backoff is currently set to 10 seconds.

    $ appsync-backoff set 20
    Backoff set to 20 seconds.

    $ appsync-backoff del
    Backoff removed

    $ appsync-backoff get
    No Backoff has been set in Memcached

    $ appsync-backoff -m 127.0.0.1 get
    No Backoff has been set in Memcached

 
