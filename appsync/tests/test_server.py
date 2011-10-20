import os
import unittest
import json
import time

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
