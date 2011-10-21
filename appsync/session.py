import time


# will move to membase or whatever
_SESSIONS = {}


def get_session(user_id):
    """Returns a dict containing the user's session info"""
    session = _SESSIONS.get(user_id)
    if session is None:
        return None
    data, timeout = session
    if timeout != 0 and timeout < time.time():
        del _SESSIONS[user_id]
        return None

    return data


def set_session(user_id, data=None, duration=None):
    """Set a session for a user

    - data: the session data
    - duration: the duration after which the session expires
    """
    if data is None:
        data = {}

    if duration is None:
        # no timeout
        timeout = 0
    else:
        timeout = time.time() + duration

    _SESSIONS[user_id] = (data, timeout)
