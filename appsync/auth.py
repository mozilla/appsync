""" AppSync Authentication
"""
import binascii
from base64 import urlsafe_b64encode as b64enc
from base64 import urlsafe_b64decode as b64dec

from webob.exc import HTTPUnauthorized


def check_auth(request):
    """Controls the Authorization header and returns the username and the
    collection.

    Raises a 401 in these cases:

    - If the header is not present or unrecognized
    - If the request path is not *owned* by that user
    - the database token

    The header is of the form:

        AppSync b64(assertion):b64(username):b64(token)

    """
    user = request.matchdict['user']
    collection = request.matchdict['collection']
    auth = request.environ.get('HTTP_AUTHORIZATION')
    mock_browserid = request.registry['mock_browserid']
    if mock_browserid:
        return user, collection, None

    if auth is None:
        raise HTTPUnauthorized()

    if not auth.startswith('AppSync '):
        raise HTTPUnauthorized('Invalid token')

    auth = auth[len('AppSync '):].strip()
    auth_part = auth.split(':')
    if len(auth_part) != 3:
        raise HTTPUnauthorized('Invalid token')

    try:
        auth_part = [b64dec(part) for part in auth_part]
    except (binascii.Error, ValueError):
        raise HTTPUnauthorized('Invalid token')

    assertion, username, dbtoken = auth_part

    # let's reject the call if the url is not owned by the user
    if user != username:
        raise HTTPUnauthorized()

    # need to verify the user signature here
    # XXX
    return user, collection, dbtoken


def create_auth(assertion, username, token):

    auth = 'AppSync %s:%s:%s' % (b64enc(assertion), b64enc(username),
                                 b64enc(token))
    return auth
