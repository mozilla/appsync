import base64
import json
import urllib

from webob.exc import HTTPBadRequest
from appsync.storage import IAppSyncDatabase


BROWSERID_VERIFY_URL = 'https://browserid.org/verify'


def get_storage(request):
    """Get the active storage backend for the given request."""
    return request.registry.getUtility(IAppSyncDatabase)


def bad_request(code, msg=''):
    """Creates a 400 response with a json body
    containing an error code and a message
    """
    return HTTPBadRequest({'code': code, 'msg': msg},
                          content_type='application/json')


def urlb64decode(data):
    data = data.replace('-', '+')
    data = data.replace('_', '+')
    pad = len(data) % 4

    if pad not in (0, 2, 3):
        raise TypeError()

    if pad == 2:
        data += '=='
    else:
        data += '='

    return base64.b64decode(data)


def verify_browserid(assertion, audience):
    """Verify the given BrowserID assertion.

    This function verifies the given BrowserID assertion.  If valid it
    returns a tuple (email, result). giving the asserted email address and
    the JSON response from the verifier.  If invalid is returns a tuple
    (None, result) givig the JSON error data from the verifier.

    Currently this function just POSTs to the browserid.org verifier service.

    WARNING: this does no HTTPS certificate checking and so is completely open
             to credential forgery.  I'll fix that eventually...

    """
    # FIXME: check the TLS certificates.
    post_data = {"assertion": assertion, "audience": audience}
    post_data = urllib.urlencode(post_data)
    try:
        resp = urllib.urlopen(BROWSERID_VERIFY_URL, post_data)
        content_length = resp.info().get("Content-Length")
        if content_length is None:
            data = resp.read()
        else:
            data = resp.read(int(content_length))
        data = json.loads(data)
    except (ValueError, IOError):
        return None, {"status": "failed", "error": "BrowserID server error"}
    if resp.getcode() != 200:
        return None, data
    if data.get("status") != "okay":
        return None, data
    if data.get("audience") != audience:
        return None, data
    return data.get("email"), data


def dummy_verify_browserid(assertion, audience):
    """Verify the given Dummy BrowserID assertion.

    This function can be used to replace verify_browserid() for testing
    purposes.  Instead of a BrowserID assertion it accepts an email as a
    string, and returns that string unchanged as the asserted identity.

    If the given assertion doesn't look like an email address, or if the
    given audience is False, then an error response is returned.
    """
    if not assertion or "@" not in assertion:
        return None, {"status": "failed", "error": "invalid assertion"}
    if not audience:
        return None, {"status": "failed", "error": "invalid audience"}
    data = {}
    data["status"] = "okay"
    data["email"] = assertion
    data["audience"] = audience
    return assertion, data
