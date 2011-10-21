from cornice import Service
from webob.exc import HTTPBadRequest
import time
import re

from appsync.application import get_applications, add_application
from appsync.session import get_session, set_session


_DOMAIN = 'browserid.org'
_OK = 'okay'
_KO = 'failed'
_VALIDITY_DURATION = 1000
_ASSERTION_MATCH = re.compile('a=(.*)')
_SESSION_DURATION = 300


#
# /verify service, that adds a user session
#
verify = Service(name='verify', path='/verify')


## XXX use Ryan's browser id pyramid plugin
@verify.post()
def verify(request):
    data = request.POST
    if 'audience' not in data or 'assertion' not in data:
        raise HTTPBadRequest()

    assertion = data['assertion']
    audience = data['audience']

    # check if audience matches assertion
    res = _ASSERTION_MATCH.search(assertion)
    if res is None or res.groups() != (audience,):
        return {'status': _KO,
                'reason': 'audience does not match'}

    assertion = assertion.split('?')[0]

    # create a new session for the given user
    set_session('tarek')  # XXX

    return {'status': _OK,
            'email': assertion,
            'audience': audience,
            'valid-until': time.time() + _VALIDITY_DURATION,
            'issuer': _DOMAIN}


#
# GET/POST for the collections data
#

def _check_session(request):
    """Controls if the user has a session"""
    # need to add auth here XXX
    # XXX need to make sure this user == the authenticated user
    user = request.matchdict['user']
    collection = request.matchdict['collection']

    session = get_session(user)
    if session is None:
        # XXX return something useful
        raise HTTPBadRequest()

    return user, collection, session


data = Service(name='data', path='/collections/{user}/{collection}')


@data.get()
def get_data(request):
    user, collection, session = _check_session(request)

    # we should use decimals everywhere XXX
    try:
        since = request.GET.get('since', '0')
        since = float(since)
    except TypeError:
        raise HTTPBadRequest()


    res = {'since': since,
           'until': time.time(),
           'applications': []}

    for app in get_applications(user, collection):
        if app['last_modified'] < since:
            continue
        res['applications'].append(app)

    return res


@data.post()
def post_data(request):
    user, collection, session = _check_session(request)
    server_time = time.time()
    try:
        apps = request.json_body
    except ValueError:
        raise HTTPBadRequest()

    # XXX what about sending back a partial report if some
    # apps are not compliant
    failures = []

    for app in apps:
        try:
            add_application(user, collection, app)
        except Exception, e:
            # failed for some reason
            failures.append((app, str(e)))

    return {'stamp': server_time}
