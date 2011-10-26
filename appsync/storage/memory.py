import time
import collections

from appsync.util import round_time


def _key(*args):
    return ':::'.join(args)


class MemDatabase(object):

    def __init__(self):
        self._apps = collections.defaultdict(list)

    def get_applications(self, user, collection, since=0):
        res = []
        for app in self._apps[_key(user, collection)]:
            if app['last_modified'] < since:
                continue
            res.append(app)
        return res

    def add_applications(self, user, collection, applications):
        key = _key(user, collection)
        for application in applications:
            self._apps[key].append(application)
