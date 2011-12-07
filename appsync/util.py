import base64
import json
import urllib

from zope.interface.registry import ComponentLookupError
from webob.exc import HTTPBadRequest
from appsync.storage import IAppSyncDatabase
from appsync.cache import IAppCache


def get_storage(request):
    """Get the active storage backend for the given request."""
    return request.registry.getUtility(IAppSyncDatabase)


def get_cache(request):
    """Get the active cache backend for the given request."""
    try:
        return request.registry.getUtility(IAppCache)
    except ComponentLookupError:
        return None


def bad_request(code, msg=''):
    """Creates a 400 response with a json body
    containing an error code and a message
    """
    return HTTPBadRequest({'code': code, 'msg': msg},
                          content_type='application/json')


def urlb64decode(data):
    data = data.replace('-', '+')
    data = data.replace('_', '+')
    pad = len(data) % 4

    if pad not in (0, 2, 3):
        raise TypeError()

    if pad == 2:
        data += '=='
    else:
        data += '='

    return base64.b64decode(data)
