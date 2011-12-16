import os
import time

from appsync.storage import IAppSyncDatabase, StorageAuthError
from appsync.tests.test_server import TestSyncApp, vep


_INI = os.path.join(os.path.dirname(__file__), 'test_mirror.ini')


class TestMirror(TestSyncApp):

    ini = _INI

    def tearDown(self):
        uris = ['storage.readwrite.sqluri', 'storage.write.sqluri']

        for uri in uris:
            sqluri = self.config.get_settings().get(uri)
            if sqluri is not None and sqluri.startswith('sqlite'):
                filename = sqluri[len('sqlite://'):]
                if os.path.exists(filename):
                    os.remove(filename)

    def test_auth(self):
        # let's make sure the slave don't check the tokens
        # because they are the master's one !
        #
        storage = self.config.registry.getUtility(IAppSyncDatabase)
        slave = storage._write
        master = storage._readwrite

        self.assertRaises(NotImplementedError, slave.verify, '', '')

        # start a session
        audience = "http://myapps.mozillalabs.com/"
        assertion = vep.DummyVerifier.make_assertion("t@m.com", audience)
        login_data = {'assertion': assertion,
                      'audience': audience}
        resp = self.app.post('/verify', login_data)
        res = resp.json

        # get the auth header
        auth = res["http_authorization"].encode("ascii")
        extra = {'HTTP_AUTHORIZATION': auth}

        # getting the collection 'blah'
        self.app.get('/collections/t@m.com/blah', extra_environ=extra,
                     status=200)

        # ok let's put some data up
        app1 = {'origin': 'app1', 'last_modified': time.time() + 0.1}
        app2 = {'origin': 'app2', 'last_modified': time.time() + 0.1}
        apps = [app1, app2]

        # write on the slave with a fake token should work
        # because we bypass its value
        slave.add_applications('t@m.com', 'blah', apps, 'faketoken')

        # which would fail on the master
        self.assertRaises(StorageAuthError, master.add_applications,
                          't@m.com', 'blah', apps, 'faketoken')
