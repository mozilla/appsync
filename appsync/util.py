from webob.exc import HTTPBadRequest
from appsync.storage import IAppSyncDatabase


def get_storage(request):
    """Get the active storage backend for the given request."""
    return request.registry.getUtility(IAppSyncDatabase)


def bad_request(code, msg=''):
    """Creates a 400 response with a json body
    containing an error code and a message
    """
    return HTTPBadRequest({'code': code, 'msg': msg},
                          content_type='application/json')
