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
    - If the user signature does not match the user

    The header is of the form:

        AppSync b64(assertion):b64(username):b64(usersig)

    """
    user = request.matchdict['user']
    collection = request.matchdict['collection']
    auth = request.environ.get('HTTP_AUTHORIZATION')

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

    assertion, username, usersig = auth_part

    # let's reject the call if the url is not owned by the user
    if user != username:
        raise HTTPUnauthorized()

    # need to verify the user signature here
    # XXX
    return user, collection


def create_auth(assertion, username):
    ## FIXME: need to generate the user signature here
    usersig = 'XXX'
    auth = 'AppSync %s:%s:%s' % (b64enc(assertion), b64enc(username),
                                 b64enc(usersig))
    return auth
