import re
import urllib

from webob.exc import HTTPBadRequest
from mozsvc.util import round_time
from appsync.views import verify
from appsync.auth import create_auth


_ASSERTION_MATCH = re.compile('a=(.*)')
_VALIDITY_DURATION = 1000
_DOMAIN = 'browserid.org'
_OK = 'okay'
_KO = 'failed'


@verify.post()
def mock_verify(request):
    data = request.POST
    if 'audience' not in data or 'assertion' not in data:
        raise HTTPBadRequest()

    assertion = data['assertion']
    audience = data['audience']

    # check if audience matches assertion
    res = _ASSERTION_MATCH.search(assertion)
    if not res or res.group(1) != audience:
        return {'status': _KO,
                'reason': 'audience does not match'}

    assertion = assertion.split('?', 1)[0]

    # XXX removing the a= header
    if assertion.startswith('a='):
        assertion = assertion[2:]

    collection_url = '/collections/%s/apps' % urllib.quote(assertion)

    auth = create_auth(assertion, assertion, 'sometoken')

    return {'status': _OK,
            'email': assertion,
            'audience': audience,
            'valid-until': round_time() + _VALIDITY_DURATION,
            'issuer': _DOMAIN,
            'collection_url': request.application_url + collection_url,
            'http_authorization': auth}
