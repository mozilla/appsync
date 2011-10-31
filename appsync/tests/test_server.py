import os
import unittest
import time
import json
from base64 import b64encode as _b64

from webtest import TestApp
from appsync import main
from pyramid import testing
from mozsvc.config import Config
from mozsvc.util import resolve_name


_INI = os.path.join(os.path.dirname(__file__), 'tests.ini')


class TestSyncApp(unittest.TestCase):
    def setUp(self):
        # creating a test application
        self.config = testing.setUp()
        self.config.include("cornice")
        self.config.include("mozsvc")
        self.config.scan("appsync.views")
        self.config.scan("appsync.tests.views")

        conf = Config(_INI)
        backend = conf.get('storage', 'backend')
        klass = resolve_name(backend)
        self.config.registry['storage'] = klass(**dict(conf.items('storage')))

        wsgiapp = self.config.make_wsgi_app()
        self.app = TestApp(wsgiapp)

    def tearDown(self):
        # XXX should look at the path in the config file
        if os.path.exists('/tmp/appsync-test.db'):
            os.remove('/tmp/appsync-test.db')

    def test_protocol(self):
        """
        To start the sync process you must have a BrowserID assertion.
        It should be an assertion from `myapps.mozillalabs.com` or another
        in a whitelist of domains.

        Send a request to:

            POST https://myapps.mozillalabs.com/apps-sync/verify

            assertion={assertion}&audience={audience}

        The response will be a JSON document, containing the same information
        as a request to `https://browserid.org/verify` but also with the keys
        (in case of a successful login) `collection_url`  and
        `authentication_header`.

        `collection_url` will be the URL where you will access the
        applications.  `authentication_header` is a value you will include
        in `Authentication: {authentication_header}` with each request.

        A request may return a 401 status code.  The `WWW-Authenticate`
        header will not be significant in this case.  Instead you should
        start the login process over with a request to

        `https://myapps.mozillalabs.com/apps-sync/verify`
        """
        # missing 'audience'  => 400
        login_data = {'assertion': 'tarek'}

        # XXX why this not working ?
        #self.app.post('/verify', login_data, status=400)

        # missing 'assertion'  => 400
        login_data = {'audience': 'tarek'}

        # XXX why this not working ?
        #self.app.post('/verify', login_data, status=400)

        # looking good, but bad assertion
        login_data = {'assertion': 'tarek', 'audience': 'bouh'}
        resp = self.app.post('/verify', login_data)
        res = resp.json

        # checking the result
        self.assertEqual(res['status'], 'failed')

        # looking good
        login_data = {'assertion': 'a=tarek?bli',
                      'audience': 'tarek?bli'}
        resp = self.app.post('/verify', login_data)
        res = resp.json

        # checking the result
        self.assertEqual(res['status'], 'okay')
        self.assertEqual(res['audience'], 'tarek?bli')
        self.assertEqual(res['email'], 'tarek')
        self.assertTrue(res['valid-until'] > time.time())
        self.assertTrue(res['issuer'], 'browserid.org')

        """
        After authenticating with the server and getting back the URL of the
        collection, request:

            GET /collections/{user}/{collection}?since=timestamp

        `since` is optional; on first sync is should be empty or left off. The
        server will return an object:

            { until: timestamp,
              incomplete: bool, applications: {origin: {...},
                                                        ...} }

        The response may not be complete if there are too many applications.
        If this is the case then `incomplete` will be true (it may be left out
        if
        the response is complete).  Another request using `since={until}` will
        get further applications (this may need to be repeated many times).

        The client should save the value of `until` and use it for subsequent
        requests.

        In the case of no new items the response will be only
        `{until: timestamp}`.

        The client should always start with this GET request and only then send
        its own updates.  It should ensure that its local timestamp is
        sensible in comparison to the value of `until`.

        Applications returned may be older than the local applications, in that
        case then the client should ignore the server's application and use
        its local copy, causing an overwrite.  The same is true for deleted
        applications; if the local installed copy has a `last_modified` date
        newer than the deleted server instance then the server instance
        should be ignored (the user reinstalled an application).

        **NOTE:** there are some conflicts that may occur, specifically
        receipts should be merged.

        When an application is added from the server the client should
        *locally* set `app.sync` to true (this is in the [application
        representation]
        (https://developer.mozilla.org/en/OpenWebApps/The_JavaScript_API
        #Application_Representation), not the manifest).

        You must always retain `last_modified` as you received it from
        the server (unless you ignore the application in favor of a
        newer local version).
        """
        # building the auth header
        auth = 'AppSync %s:%s:%s' % (_b64('a=tarek'), _b64('tarek'),
                                     _b64('somesig'))

        extra = {'HTTP_AUTHORIZATION': auth}

        # getting the collection 'blah'
        data = self.app.get('/collections/tarek/blah',
                            extra_environ=extra).json

        # what did we get ?
        self.assertTrue(data['until'] <= time.time() + 0.1)
        self.assertEqual(data['since'], 0)
        self.assertEqual(len(data['applications']), 0)

        # getting the collection 'blah' since 5 min ago
        since = time.time() - 300
        data2 = self.app.get('/collections/tarek/blah?since=%s' % since,
                             extra_environ=extra).json

        # what did we get ?
        self.assertTrue(data2['until'] <= time.time() + 0.1)

        # XXX we need to use Decimal everywhere on server-side
        self.assertTrue(since - data2['since'] < 0.2)
        self.assertEqual(len(data['applications']), 0)

        # ok let's put some data up
        app1 = {'last_modified': time.time() + 0.1}
        app2 = {'last_modified': time.time() + 0.1}

        apps = json.dumps([app1, app2])

        res = self.app.post('/collections/tarek/blah', params=apps,
                            extra_environ=extra,
                            content_type='application/json')

        # see if we got them
        data = self.app.get('/collections/tarek/blah',
                            extra_environ=extra).json

        # what did we get ?
        self.assertTrue(data['until'] <= time.time() + 0.1)
        self.assertEqual(data['since'], 0)
        self.assertEqual(len(data['applications']), 2)

        # let's delete some stuff
        """
        POST /collections/user/collection?delete

        body (JSON)

            {client: client_id, reason: optional text reason}

        Deletes the collection

        On a GET you'll get back
            {collection_deleted: {client: client_id,
                                  reason: optional text reason}}

        The client should inform the user, ask for
        re-authentication via browserid(maybe?).  Further POSTs
        will remove the deleted status

        Clients should always log out after doing this deletion.
        """
        delete = {'client_id': 'client1',
                  'reason': 'well...'}

        self.app.post('/collections/tarek/blah?delete',
                      extra_environ=extra, params=json.dumps(delete),
                      content_type='application/json')

        # see if we got them
        data = self.app.get('/collections/tarek/blah',
                            extra_environ=extra).json

        self.assertEquals(['collection_deleted'], data.keys())
