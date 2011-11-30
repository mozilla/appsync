import urllib
import time
try:
    import simplejson as json
except ImportError:
    import json     # NOQA

from cornice import Service
from mozsvc.util import round_time
from webob import exc

from appsync.util import get_storage, bad_request
from appsync.storage import CollectionDeletedError
from appsync.auth import create_auth, check_auth
from appsync.respcodes import (INVALID_JSON, INVALID_SINCE_VALUE,
                               MISSING_VALUE)


#
# /verify service, that adds a user session
#
verify_desc = """\
To start the sync process you must have a BrowserID assertion.

It should be an assertion from `myapps.mozillalabs.com` or another in
a whitelist of domains.
"""


verify = Service(name='verify', path='/verify', description=verify_desc)


@verify.post()
def verify_(request):
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
        raise bad_request(MISSING_VALUE)

    assertion = data['assertion']
    audience = data['audience']

    storage = get_storage(request)

    res = storage.verify(assertion, audience)
    if not res or not res[0]:
        resp = {'status': 'failed'}
        if res and res[1]:
            resp.update(res[1])
        return resp
    email, dbtoken = res

    resp = {}
    resp['email'] = email
    collection_url = '/collections/%s/apps' % urllib.quote(email)
    resp['collection_url'] = request.application_url + collection_url
    resp['http_authorization'] = create_auth(assertion, email, dbtoken)
    # XXX: This needs to return the browserid verification data
    #      but that info is not provided by the storage backend.
    #      Stubbing it out for now.
    resp['status'] = 'okay'
    resp['audience'] = audience
    resp['valid-until'] = time.time() + 5 * 60
    resp['issuer'] = 'browserid.org'
    return resp

#
# GET/POST for the collections data
#


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
         uuid: someuniquevalue,  # using a timestamp XXXX
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
    user, collection, dbtoken = check_auth(request)

    try:
        since = request.GET.get('since', '0')
        since = round_time(since)
    except TypeError:
        raise bad_request(INVALID_SINCE_VALUE)
    except ValueError:
        print 'Bad since', repr(since)
        raise bad_request(INVALID_SINCE_VALUE,
                          'Invalid value for since: %r' % since)

    if since.is_nan():
        raise bad_request(INVALID_SINCE_VALUE,
                          'Got NaN value for since')

    storage = get_storage(request)

    res = {'since': since,
           'uuid': storage.get_uuid(user, collection, dbtoken)}
    until = -1
    apps = []
    try:
        for index, (last_modified, app) in enumerate(
                storage.get_applications(user, collection, since,
                                         token=dbtoken)):
            if last_modified > until:
                until = last_modified

            apps.append(app)

        res['applications'] = apps
        res['until'] = until

    except CollectionDeletedError, e:
        return {'collection_deleted': {'reason': e.reason,
                                       'client_id': e.client_id}}

    return res


@data.post()
def post_data(request):
    """The client should keep track of the last time it sent updates to the
    server, and send updates when there are newer applications.

    **NOTE:** there is a case when an update might be lost because of an
    update from another device; this would be okay except that the client
    doesn't know it needs to re-send that update.  How do we confirm that ?

    The updates are sent with::

        POST /collections/{user}/{collection}?lastget=somedate

        {origin: {...}, ...}

    Each object must have a `last_modified` key.

    The response is only::

        {received: timestamp}

    XXX
    if lastget (timestamp) was provided and the collection has been changed
    since that date, we send back a 412 Precondition Failed.

    """
    user, collection, dbtoken = check_auth(request)
    server_time = round_time()
    storage = get_storage(request)

    if 'delete' in request.params:
        # we were asked to delete the collection
        try:
            info = request.json_body
        except ValueError:
            raise bad_request(INVALID_JSON)

        if 'client_id' not in info:
            raise bad_request(MISSING_VALUE)

        client_id = info['client_id']
        reason = info.get('reason', '')
        storage.delete(user, collection, client_id, reason, token=dbtoken)
        return {'received': server_time}

    elif 'lastget' in request.params:
        last_get = round_time(float(request.params['lastget']))
        last_modified = storage.get_last_modified(user, collection,
                                                  token=dbtoken)
        if last_modified > last_get:
            raise exc.HTTPPreconditionFailed()

    try:
        apps = request.json_body
    except ValueError:
        raise bad_request(INVALID_JSON)

    # in case this fails, the error will get logged
    # and the user will get a 503 (empty body)

    storage.add_applications(user, collection, apps, token=dbtoken)

    return {'received': server_time}


heartbeat = Service(name='heartbeat', path='/__heartbeat__')


@heartbeat.get()
def check_health(request, renderer='string'):
    """Checks that the server is up"""
    # XXX See if we want to add a backend check here
    # Services Ops would say no
    return 'OK'
