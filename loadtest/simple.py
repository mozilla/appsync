import random
import json
import unittest
import time

from funkload.FunkLoadTestCase import FunkLoadTestCase
from funkload.utils import Data

try:
    import vep
except ImportError:
    print 'You need to install PyVEP'
    raise

class SimpleTest(FunkLoadTestCase):

    def setUp(self):
        self.root = self.conf_get('main', 'url')
        self.vusers = int(self.conf_get('main', 'vusers'))

    def test_something(self):
        # most clients do polling
        pickone = ['_polling'] * 10

        # some actually add some content
        pickone += ['_content'] * 3

        # and a very few delete stuff
        #pickone += ['_delete'] * 1

        chosen = random.choice(pickone)
        return getattr(self, chosen)()

    def start_session(self):
        uid = 'user%d@moz.com' % random.randint(0, self.vusers-1)
        audience = 'https://myapps.mozillalabs.com'
        assertion = vep.DummyVerifier.make_assertion(uid, audience)
        params = [['audience', audience],
                  ['assertion', assertion]]
        resp = self.post(self.root + '/verify', params=params)
        self.assertEquals(resp.code, 200)
        res = json.loads(resp.body)
        auth = res['http_authorization']
        self.setHeader('Authorization', auth)
        return '%s/collections/%s/apps' % (self.root, uid)

    #
    # The actual tests...
    #
    def _polling(self):
        apps_url = self.start_session()
        myapps = json.loads(self.get(apps_url).body)
        self.assertTrue('applications' in myapps)

    def _delete(self):
        apps_url = self.start_session()
        myapps = json.loads(self.get(apps_url).body)
        if len(myapps['application']) > 0:
            # let's delete them !
            self.post(apps_url + '?delete=true')

    def _content(self):
        apps_url = self.start_session()

        # filling with some data
        # XXX We need realistic stuff here
        for i in range(10):
            app1 = {'origin': 'app1-%d' % i ,
                    'last_modified': time.time() + 0.1}
            app2 = {'origin': 'app2-%d' % i,
                    'last_modified': time.time() + 0.1}
            apps = json.dumps([app1, app2])

            apps = Data('application/json', apps)
            resp = self.post(apps_url, params=apps)
            self.assertEquals(resp.code, 200)
            res = json.loads(resp.body)
            self.assertTrue('received' in res)

        # checking what we have
        myapps = json.loads(self.get(apps_url).body)
        self.assertEquals(len(myapps['applications']), 20)
