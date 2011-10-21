import time
import collections


# that's where we want to hook Sauropod
_APPS = collections.defaultdict(list)


def _key(*args):
    return ':::'.join(args)


class Application(dict):
    def __init__(self):
        self['last_modified'] = time.time() - 10


def get_applications(user, collection):
    return _APPS[_key(user, collection)]


def add_application(user, collection, application):
    key = _key(user, collection)
    _APPS[key].append(application)
