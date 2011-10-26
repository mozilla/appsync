import time
import collections


# that's where we want to hook Sauropod
_APPS = collections.defaultdict(list)


def _key(*args):
    return ':::'.join(args)


class Application(dict):
    def __init__(self):
        self['last_modified'] = time.time() - 10


def get_applications(user, collection, since=0):
    res = []
    for app in _APPS[_key(user, collection)]:
        if app['last_modified'] < since:
            continue
        res.append(app)
    return res


def add_applications(user, collection, applications):
    key = _key(user, collection)
    for application in applications:
        _APPS[key].append(application)
