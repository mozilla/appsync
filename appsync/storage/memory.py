import collections
from appsync.storage import CollectionDeletedError


def _key(*args):
    return ':::'.join(args)


class MemDatabase(object):

    def __init__(self):
        self._apps = collections.defaultdict(list)
        self._deleted_apps = {}

    def delete(self, user, collection, client_id, reason=''):
        self._apps[_key(user, collection)] = []
        self._deleted_apps[_key(user, collection)] = client_id, reason

    def get_applications(self, user, collection, since=0):
        key = _key(user, collection)
        if key in self._deleted_apps:
            # deleted
            raise CollectionDeletedError(*self._deleted_apps[key])

        res = []
        for app in self._apps[_key(user, collection)]:
            if app['last_modified'] < since:
                continue
            res.append(app)
        return res

    def add_applications(self, user, collection, applications):
        key = _key(user, collection)
        if key in self._deleted_apps:
            # undelete
            del self._deleted_apps[key]

        for application in applications:
            self._apps[key].append(application)
