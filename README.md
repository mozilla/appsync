== App Sync

This implements the [Open Web
Application](https://apps.mozillalabs.com) synchronization protocol.
The client is implemented in [the main openwebapps
repository](https://github.com/mozilla/openwebapps).

=== Testing

To run the server in a configuration that is fairly equivalent to the
https://myapps.mozillalabs.com setup, use:

    $ git clone https://github.com/mozilla/openwebapps.git
    $ export OPENWEBAPPS=$(pwd)/openwebapps
    $ git clone https://github.com/mozilla/appsync.git
    $ cd appsync
    $ pip -E test-env install -r prod-reqs.txt
    $ ./test-env/bin/paster serve etc/appsync-dev.ini -n myapps --reload
