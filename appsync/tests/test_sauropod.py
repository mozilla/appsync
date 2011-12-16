import os
import collections
import json

from webob.dec import wsgify
from appsync.tests.test_server import TestSyncApp
import wsgi_intercept
from vep.verifiers.dummy import DummyVerifier
import vep

from appsync.storage import IAppSyncDatabase
from appsync.tests.support import memcache_up


def install_opener():
    # httplib patch
    from wsgi_intercept.httplib_intercept import install
    install()

    # requests' patch
    from requests.packages.urllib3 import connectionpool

    connectionpool.old_http = connectionpool.HTTPConnection
    connectionpool.HTTPConnection = wsgi_intercept.WSGI_HTTPConnection

    connectionpool.old_https = connectionpool.HTTPSConnection
    connectionpool.HTTPSConnection = wsgi_intercept.WSGI_HTTPSConnection

    # we need settimeout()
    wsgi_intercept.wsgi_fake_socket.settimeout = lambda self, timeout: None


def uninstall_opener():
    # httplib unpatch
    from wsgi_intercept.httplib_intercept import uninstall
    uninstall()
    # requests' unpatch
    from requests.packages.urllib3 import connectionpool
    connectionpool.HTTPConnection = connectionpool.old_http
    connectionpool.HTTPSConnection = connectionpool.old_https


class FakeSauropod(object):

    _data = collections.defaultdict(dict)
    hits = 0

    @classmethod
    def clear(cls):
        cls._data.clear()
        cls.hits = 0

    @classmethod
    def incr_hit(cls):
        cls.hits += 1

    def __init__(self):
        self.verif = DummyVerifier()

    @wsgify
    def __call__(self, request):
        response = request.response

        if request.path_info == '/session/start':
            assertion = request.params.get("assertion")
            audience = request.params.get("audience")

            if assertion is None or audience is None:
                response.status = 401
                return response

            try:
                self.verif.verify(assertion, audience)["email"]
            except (ValueError, vep.TrustError):
                response.status = 401
                return response

            response.body = 'sessionid'
            return response
        elif (request.path_info.startswith('/app') and
              request.method in ('GET', 'PUT', 'DELETE')):
            parts = request.path_info.split('/')
            user = parts[-3]
            key = parts[-1]
            if request.method == 'GET':
                try:
                    response.body = json.dumps({'value':
                        self._data[user][key]})
                except KeyError:
                    response.body = '{}'
                response.status = 200
                self.incr_hit()
            elif request.method == 'PUT':
                self._data[user][key] = request.POST['value']
                response.status = 200
            elif request.method == 'DELETE':
                del self._data[user][key]
                response.status = 200

            return response

        raise NotImplementedError('%s %s' % (request.method,
                                             request.path_info))


_INI = os.path.join(os.path.dirname(__file__), 'test_sauropod.ini')


class TestSauropod(TestSyncApp):

    ini = _INI

    def setUp(self):
        super(TestSauropod, self).setUp()
        install_opener()
        wsgi_intercept.add_wsgi_intercept('sauropod', 9999, FakeSauropod)

    def tearDown(self):
        FakeSauropod.clear()
        wsgi_intercept.remove_wsgi_intercept('sauropod', 9999)
        uninstall_opener()
        super(TestSyncApp, self).tearDown()

    def test_hits(self):
        # do we have memcached running ?
        if not memcache_up():
            return

        # running with memcached
        current = FakeSauropod.hits
        self.test_protocol()
        hits_with_cache = FakeSauropod.hits - current

        # reset the data
        FakeSauropod.clear()

        # let's deactivate the cache
        storage = self.config.registry.getUtility(IAppSyncDatabase)
        current = FakeSauropod.hits
        old = storage.cache
        storage.cache = None
        try:
            self.test_protocol()
        finally:
            storage.cache = old

        hits_no_cache = FakeSauropod.hits - current

        # when cache is enabled, we hits more than two times the DB
        self.assertTrue(hits_with_cache * 2 < hits_no_cache)
