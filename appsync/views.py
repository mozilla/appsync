from cornice import Service
from webob.exc import HTTPBadRequest
import re
import urllib

from appsync.application import get_applications, add_applications
from appsync.session import get_session, set_session
from appsync.util import round_time


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
## Note: this is the debugging/mock verification
@verify.post(renderer='simplejson')
def verify(request):
    data = request.POST
    if 'audience' not in data or 'assertion' not in data:
        raise HTTPBadRequest()

    assertion = data['assertion']
    audience = data['audience']

    # check if audience matches assertion
    res = _ASSERTION_MATCH.search(assertion)
    if res and res.group(1) != audience:
        return {'status': _KO,
                'reason': 'audience does not match'}

    assertion = assertion.split('?')[0]

    # create a new session for the given user
    set_session(assertion)  # XXX

    collection_url = '/collections/%s/apps' % urllib.quote(assertion)

    return {'status': _OK,
            'email': assertion,
            'audience': audience,
            'valid-until': round_time() + _VALIDITY_DURATION,
            'issuer': _DOMAIN,
            'collection_url': request.application_url + collection_url}


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


@data.get(renderer='simplejson')
def get_data(request):
    user, collection, session = _check_session(request)

    # we should use decimals everywhere XXX
    try:
        since = request.GET.get('since', '0')
        since = round_time(since)
    except TypeError:
        raise HTTPBadRequest()

    res = {'since': since,
           'until': round_time()}

    res['applications'] = get_applications(user, collection, since)
    return res


@data.post(renderer='simplejson')
def post_data(request):
    user, collection, session = _check_session(request)
    server_time = round_time()
    try:
        apps = request.json_body
    except ValueError:
        raise HTTPBadRequest()

    # in case this fails, the error will get logged
    # and the user will get a 503 (empty body)
    add_applications(user, collection, apps)

    return {'received': server_time}
