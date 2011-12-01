from pylibmc import Client
from _pylibmc import MemcachedError
from zope.interface import Interface, implements


class CacheError(Exception):
    pass


class IAppCache(Interface):
    def get(self, key):
        return self._mc.get(self._key(key))

    def set(self, key, value):
        return self._mc.set(self._key(key), value)


class Cache(object):

    implements(IAppCache)

    def __init__(self, **options):
        self.servers = [server.strip()
                        for server in options['servers'].split(',')]
        self.prefix = options['prefix']
        self._mc = Client(self.servers)

    def _key(self, *key):
        return ':'.join([self.prefix] + list(key))

    def get(self, key):
        try:
            return self._mc.get(self._key(key))
        except MemcachedError, e:
            raise CacheError(e.message)

    def set(self, key, value):
        return self._mc.set(self._key(key), value)
