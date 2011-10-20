from cornice import Service
from webob.exc import HTTPBadRequest
import time
import re

from appsync.backend import get_applications


_DOMAIN = 'browserid.org'
_OK = 'okay'
_KO = 'failed'
_VALIDITY_DURATION = 1000
_ASSERTION_MATCH = re.compile('a=(.*)')


verify = Service(name='verify', path='/verify')


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

    # XXX push something into some session

    return {'status': _OK,
            'email': assertion,
            'audience': audience,
            'valid-until': time.time() + _VALIDITY_DURATION,
            'issuer': _DOMAIN}


data = Service(name='data', path='/collections/{user}/{collection}')


@data.get()
def get_data(request):
    # we should use decimals everywhere XXX
    #
    # XXX need to control the session here
    try:
        since = request.GET.get('since', '0')
        since = float(since)
    except TypeError:
        raise HTTPBadRequest()

    # XXX need to make sure this user == the authenticated user
    user = request.matchdict['user']
    collection = request.matchdict['collection']

    res = {'since': since,
           'until': time.time(),
           'applications': []}

    for app in get_applications(user, collection):
        if app['last_modified'] < since:
            continue
        res['applications'].append(app)

    return res
