import random
import json
import unittest
import time

from funkload.FunkLoadTestCase import FunkLoadTestCase
from funkload.utils import Data


class SimpleTest(FunkLoadTestCase):

    def setUp(self):
        self.root = self.conf_get('main', 'url')
        self.vusers = int(self.conf_get('main', 'vusers'))

    def test_simple_session(self):

        assertion = 'user%d@moz.com' % random.randint(0, self.vusers-1)
        audience = 'http://myapps.mozillalabs.com/'
        params = [['audience', audience],
                  ['assertion', assertion]]

        # creating a session
        resp = self.post(self.root + '/verify', params=params)
        self.assertEquals(resp.code, 200)

        res = json.loads(resp.body)
        auth = res['http_authorization']

        # now doing some work
        self.setHeader('Authorization', auth)

        # filling with some data
        # XXX We need realistic stuff here
        for i in range(10):
            app1 = {'origin': 'app1-%d' % i ,
                    'last_modified': time.time() + 0.1}
            app2 = {'origin': 'app2-%d' % i,
                    'last_modified': time.time() + 0.1}
            apps = json.dumps([app1, app2])
            apps_url = '%s/collections/%s/apps' % (self.root, assertion)
            apps = Data('application/json', apps)
            resp = self.post(apps_url, params=apps)
            self.assertEquals(resp.code, 200)
            res = json.loads(resp.body)
            self.assertTrue('received' in res)

        # checking what we have
        myapps = json.loads(self.get(apps_url).body)
        self.assertEquals(len(myapps['applications']), 20)
