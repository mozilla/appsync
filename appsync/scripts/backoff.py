import sys
try:
    import pylibmc
except ImportError:
    print("You need to install pylibmc")
    sys.exit(1)

from optparse import OptionParser

_KEY = 'appsync:X-Sync-Poll'


def main():
    usage = "usage: %prog [options] get|set value|del"
    parser = OptionParser(usage=usage)
    parser.add_option("-m", "--memcached", dest="memcached",
                      help="Memcache server",
                      default="127.0.0.1:11211")
    options, args = parser.parse_args()

    if len(args) < 1:
        parser.error("You need at least one argument")

    action = args[0]

    if action not in ('get', 'set', 'del'):
        parser.print_help()
        sys.exit(1)

    if action == 'set' and len(args) < 2:
        parser.print_help()
        sys.exit(1)

    try:
        client = pylibmc.Client([options.memcached])
    except ValueError:
        parser.error('Invalid server %s' % options.memcached)

    if action == 'get':
        value = client.get(_KEY)
        if value is None:
            print("No Backoff has been set in Memcached")
            sys.exit(0)
        else:
            print("The Backoff is currently set to %s seconds." % value)

    elif action == 'set':
        try:
            value = int(args[1])
        except ValueError:
            print("%r is not a number of seconds" % args[1])
            sys.exit(1)

        client.set(_KEY, value)
        print("Backoff set to %d seconds." % value)
        sys.exit(0)
    elif action == 'del':
        client.delete(_KEY)
        print("Backoff removed")
        sys.exit(0)


if __name__ == '__main__':
    main()
