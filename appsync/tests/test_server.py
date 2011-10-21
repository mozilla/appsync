import os
import unittest
import time
import json
from webtest import TestApp
from appsync import main


_INI = os.path.join(os.path.dirname(__file__), 'tests.ini')


class TestSyncApp(unittest.TestCase):
    def setUp(self):
        globs = {'__file__': _INI}
        settings = {}
        self.app = TestApp(main(globs, **settings))

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
        login_data = {'assertion': 'blah'}
        self.app.post('/verify', login_data, status=400)

        # missing 'assertion'  => 400
        login_data = {'audience': 'blah'}
        self.app.post('/verify', login_data, status=400)

        # looking good, but bad assertion
        login_data = {'assertion': 'blah', 'audience': 'bouh'}
        resp = self.app.post('/verify', login_data)
        res = resp.json

        # checking the result
        self.assertEqual(res['status'], 'failed')

        # looking good
        login_data = {'assertion': 'a=blah?bli',
                      'audience': 'blah?bli'}
        resp = self.app.post('/verify', login_data)
        res = resp.json

        # checking the result
        self.assertEqual(res['status'], 'okay')
        self.assertEqual(res['audience'], 'blah?bli')
        self.assertEqual(res['email'], 'a=blah')
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
        # getting the collection 'blah'
        data = self.app.get('/collections/tarek/blah').json

        # what did we get ?
        self.assertTrue(data['until'] <= time.time())
        self.assertEqual(data['since'], 0)
        self.assertEqual(len(data['applications']), 0)

        # getting the collection 'blah' since 5 min ago
        since = time.time() - 300
        data2 = self.app.get('/collections/tarek/blah?since=%s' % since).json

        # what did we get ?
        self.assertTrue(data2['until'] <= time.time())

        # XXX we need to use Decimal everywhere on server-side
        self.assertTrue(since - data2['since'] < 0.2)
        self.assertEqual(len(data['applications']), 0)

        # ok let's put some data up
        app1 = {'last_modified': time.time()}
        app2 = {'last_modified': time.time()}

        apps = json.dumps([app1, app2])
        res = self.app.post('/collections/tarek/blah', params=apps)

        # see if we got them
        data = self.app.get('/collections/tarek/blah').json

        # what did we get ?
        self.assertTrue(data['until'] <= time.time())
        self.assertEqual(data['since'], 0)
        self.assertEqual(len(data['applications']), 2)
