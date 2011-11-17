import os
import unittest
import time
import json
from base64 import b64encode as _b64

from webtest import TestApp
from webob import exc
from webob.dec import wsgify
from pyramid import testing
from mozsvc.config import load_into_settings


_INI = os.path.join(os.path.dirname(__file__), 'tests.ini')


class CatchErrors(object):
    def __init__(self, app):
        self.app = app

    @wsgify
    def __call__(self, request):
        try:
            return request.get_response(self.app)
        except exc.HTTPException, e:
            return e


class TestSyncApp(unittest.TestCase):
    def setUp(self):
        self.config = testing.setUp()

        # creating a test application
        settings = {}
        load_into_settings(_INI, settings)
        self.config.add_settings(settings)
        self.config.include("appsync")
        self.config.scan("appsync.tests.views")

        wsgiapp = self.config.make_wsgi_app()
        app = CatchErrors(wsgiapp)
        self.app = TestApp(app)

    def tearDown(self):
        # XXX should look at the path in the config file
        if os.path.exists('/tmp/appsync-test.db'):
            os.remove('/tmp/appsync-test.db')

    def test_protocol(self):
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
        delete = {'client_id': 'client1',
                  'reason': 'well...'}

        self.app.post('/collections/tarek/blah?delete',
                      extra_environ=extra, params=json.dumps(delete),
                      content_type='application/json')

        # see if we got them
        data = self.app.get('/collections/tarek/blah',
                            extra_environ=extra).json

        self.assertEquals(['collection_deleted'], data.keys())

        # in case we delete and recreate the collection
        # the uuid needs to change

        # creating some data
        self.app.post('/collections/tarek/blah',
                      extra_environ=extra, params=apps,
                      content_type='application/json')
        data = self.app.get('/collections/tarek/blah',
                            extra_environ=extra).json

        uuid = data['uuid']

        # deleting that collection
        delete = {'client_id': 'client1',
                  'reason': 'well...'}

        self.app.post('/collections/tarek/blah?delete',
                      extra_environ=extra, params=json.dumps(delete),
                      content_type='application/json')

        # see if we got them
        data = self.app.get('/collections/tarek/blah',
                            extra_environ=extra).json

        self.assertEquals(['collection_deleted'], data.keys())

        # creating some data again
        self.app.post('/collections/tarek/blah',
                      extra_environ=extra,
                      params=apps,
                      content_type='application/json')

        data = self.app.get('/collections/tarek/blah',
                            extra_environ=extra).json

        new_uuid = data['uuid']
        self.assertNotEqual(uuid, new_uuid)

        # now let's try the 412
        # if lastget is used it will compare it with the
        # timestamp of the last change
        now = time.time() - 100

        # let's change the data
        self.app.post('/collections/tarek/blah',
                      extra_environ=extra,
                      params=apps,
                      content_type='application/json')

        # let's change it again with lastget < the last change
        # we should get a 412
        self.app.post('/collections/tarek/blah?lastget=%s' % now,
                      extra_environ=extra,
                      params=apps,
                      content_type='application/json',
                      status=412)
