import time
import collections

from sqlalchemy.exc import OperationalError, TimeoutError
from sqlalchemy import create_engine

from appsync.util import round_time


_TABLES = []


def _key(*args):
    return ':::'.join(args)


def safe_execute(engine, *args, **kwargs):
    try:
        return engine.execute(*args, **kwargs)
    except (OperationalError, TimeoutError), exc:
        # beyond this point, the connector is removed from the pool
        retry = '2013' in str(exc)
    try:
        if retry:
            return engine.execute(*args, **kwargs)
        else:
            # re-raise
            raise exc
    except (OperationalError, TimeoutError), exc:
        err = traceback.format_exc()
        logger.error(err)
        raise BackendError(str(exc))


class SQLDatabase(object):

    def __init__(self, **options):
        #sqlkw = {'pool_size': int(options.get('pool_size', 1)),
        #         'pool_recycle': int(options.get('pool_recycle', 3600)),
        #         'logging_name': 'appsync'}
        sqlkw = {}

        self.engine = create_engine(options['sqluri'], **sqlkw)
        for table in _TABLES:
            table.metadata.bind = engine
            if options.get('create_tables', True):
                table.create(checkfirst=True)

    def _execute(self, *args, **kw):
        return safe_execute(self.engine, *args, **kw)

    def get_applications(self, user, collection, since=0):
        raise NotImplementedError()

    def add_applications(self, user, collection, applications):
        raise NotImplementedError()
