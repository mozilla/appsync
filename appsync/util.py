from webob.exc import HTTPBadRequest


def get_storage(request):
    return request.registry['storage']


def bad_request(code, msg=''):
    """Creates a 400 response with a json body
    containing an error code and a message
    """
    return HTTPBadRequest({'code': code, 'msg': msg},
                          content_type='application/json')
