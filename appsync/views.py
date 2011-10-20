from cornice import Service
from webob.exc import HTTPBadRequest
import time
import re


_DOMAIN = 'browserid.org'
_OK = 'okay'
_KO = 'failed'
_VALIDITY_DURATION = 1000
_ASSERTION_MATCH = re.compile('a=(.*)')


verify = Service(name='appsync', path='/verify')


@verify.api(request_method='POST')
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
