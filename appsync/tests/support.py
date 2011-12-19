import pylibmc


def memcache_up(server='127.0.0.1'):
    try:
        client = pylibmc.Client([server])
        client.set('test', '1')
        return client.get('test') == '1'
    except Exception:
        return False
