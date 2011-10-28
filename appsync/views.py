import re
import urllib

from webob.exc import HTTPBadRequest
from cornice import Service
from mozsvc.util import round_time

from appsync.util import get_storage
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
verify_desc = """\
To start the sync process you must have a BrowserID assertion.

It should be an assertion from `myapps.mozillalabs.com` or another in
a whitelist of domains."""


verify = Service(name='verify', path='/verify',
                 description=verify_desc)


## XXX use Ryan's browser id pyramid plugin
## Note: this is the debugging/mock verification
@verify.post()
def verify(request):
    """The request takes 2 options:

    - assertion
    - audience

    The response will be a JSON document, containing the same information
    as a request to `https://browserid.org/verify` but also with the keys
    (in case of a successful login) `collection_url`  and
    `authentication_header`.

    `collection_url` will be the URL where you will access the
    applications.  `authentication_header` is a value you will include
    in `Authentication: {authentication_header}` with each request.

    A request may return a 401 status code.  The `WWW-Authenticate`
    header will not be significant in this case.  Instead you should
    start the login process over with a request to

    `https://myapps.mozillalabs.com/apps-sync/verify`
    """
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

    assertion = assertion.split('?')[0]

    # XXX removing the a= header
    if assertion.startswith('a='):
        assertion = assertion[2:]

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


data = Service(name='data', path='/collections/{user}/{collection}',
               description='Used to get and set the apps')


@data.get()
def get_data(request):
    """After authenticating with the server and getting back the URL of the
    collection, request::

        GET /collections/{user}/{collection}?since=timestamp

    `since` is optional; on first sync is should be empty or left off. The
    server will return an object::

        {until: timestamp,
         incomplete: bool, applications: {origin: {...},
                                                   ...} }

    The response may not be complete if there are too many applications.
    If this is the case then `incomplete` will be true (it may be left out
    if
    the response is complete).  Another request using `since={until}` will
    get further applications (this may need to be repeated many times).

    The client should save the value of `until` and use it for subsequent
    requests.

    In the case of no new items the response will be only::

        {until: timestamp}

    The client should always start with this GET request and only then send
    its own updates.  It should ensure that its local timestamp is
    sensible in comparison to the value of `until`.

    Applications returned may be older than the local applications, in that
    case then the client should ignore the server's application and use
    its local copy, causing an overwrite.  The same is true for deleted
    applications; if the local installed copy has a `last_modified` date
    newer than the deleted server instance then the server instance
    should be ignored (the user reinstalled an application).

    **NOTE:** there are some conflicts that may occur, specifically
    receipts should be merged.

    When an application is added from the server the client should
    *locally* set `app.sync` to true (this is in the [application
    representation]
    (https://developer.mozilla.org/en/OpenWebApps/The_JavaScript_API
    #Application_Representation), not the manifest).

    You must always retain `last_modified` as you received it from
    the server (unless you ignore the application in favor of a
    newer local version).
    """
    user, collection, session = _check_session(request)

    try:
        since = request.GET.get('since', '0')
        since = round_time(since)
    except TypeError:
        raise HTTPBadRequest()

    res = {'since': since,
           'until': round_time()}

    storage = get_storage(request)
    res['applications'] = storage.get_applications(user, collection, since)
    return res


@data.post()
def post_data(request):
    """The client should keep track of the last time it sent updates to the
    server, and send updates when there are newer applications.

    **NOTE:** there is a case when an update might be lost because of an
    update from another device; this would be okay except that the client
    doesn't know it needs to re-send that update.  How do we confirm that ?

    The updates are sent with::

        POST /collections/{user}/{collection}

        {origin: {...}, ...}

    Each object must have a `last_modified` key.

    The response is only::

        {received: timestamp}

    """
    user, collection, session = _check_session(request)
    server_time = round_time()
    try:
        apps = request.json_body
    except ValueError:
        raise HTTPBadRequest()

    # in case this fails, the error will get logged
    # and the user will get a 503 (empty body)
    storage = get_storage(request)
    storage.add_applications(user, collection, apps)

    return {'received': server_time}
