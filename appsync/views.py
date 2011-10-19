from cornice import Service
from webob.exc import HTTPBadRequest
import time


_DOMAIN = 'browserid.org'
_OK = 'okay'
_VALIDITY_DURATION = 1000

appsync = Service(name='appsync', path='/verify')


@appsync.api(request_method='POST')
def hello(request):
    data = request.POST
    if 'audience' not in data or 'assertion' not in data:
        raise HTTPBadRequest()

    # XXX push something into some session

    return {'status': _OK,
            'email': data['assertion'],
            'audience': data['audience'],
            'valid-until': time.time() + _VALIDITY_DURATION,
            'issuer': _DOMAIN}
