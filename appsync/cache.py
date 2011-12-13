from pylibmc import Client, NotFound, ThreadMappedPool
from pylibmc import Error as MemcachedError
import threading

from zope.interface import Interface, implements


class CacheError(Exception):
    pass


class IAppCache(Interface):

    def cleanup():
        """Cleanup the pool"""

    def flush_all():
        """Flush all"""

    def get(key):
        """get a key"""

    def delete(key):
        """"Delete a key"""

    def incr(key, size=1):
        """Increment a counter"""

    def set(key, value, time=0):
        """Set a key"""

    def get_set(key, func):
        """GetSet a key"""


class Cache(object):
    """ Helpers on the top of pylibmc
    """
    implements(IAppCache)

    def __init__(self, **options):
        self.servers = [server.strip()
                        for server in options['servers'].split(',')]
        self.prefix = options['prefix']
        self._client = Client(self.servers)
        self.pool = ThreadMappedPool(self._client)
        # using a locker to avoid race conditions
        # when several clients for the same user
        # get/set the cached data
        self._locker = threading.RLock()

    def _key(self, *key):
        return ':'.join([self.prefix] + list(key))

    def cleanup(self):
        self.pool.pop(thread.get_ident(), None)

    def flush_all(self):
        with self.pool.reserve() as mc:
            mc.flush_all()

    def get(self, key):
        key = self._key(key)

        with self.pool.reserve() as mc:
            try:
                return mc.get(key)
            except MemcachedError, err:
                # memcache seems down
                raise CacheError(str(err))

    def delete(self, key):
        key = self._key(key)

        with self.pool.reserve() as mc:
            try:
                return mc.delete(key)
            except NotFound:
                return False
            except MemcachedError, err:
                # memcache seems down
                raise CacheError(str(err))

    def incr(self, key, size=1):
        key = self._key(key)

        with self.pool.reserve() as mc:
            try:
                return mc.incr(key, size)
            except NotFound:
                return mc.set(key, size)
            except MemcachedError, err:
                raise CacheError(str(err))

    def set(self, key, value, time=0):
        key = self._key(key)

        with self.pool.reserve() as mc:
            try:
                if not mc.set(key, value, time=time):
                    raise CacheError()
            except MemcachedError, err:
                raise CacheError(str(err))

    def get_set(self, key, func):
        res = self.get(key)
        if res is None:
            res = func()
            self.set(key, res)
        return res
