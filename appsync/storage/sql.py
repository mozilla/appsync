import traceback

import simplejson as json
from sqlalchemy.exc import OperationalError, TimeoutError
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base, Column
from sqlalchemy import Integer, String, Text

from mozsvc.exceptions import BackendError

from appsync.util import round_time
from appsync import logger


_TABLES = []
_Base = declarative_base()


class Application(_Base):
    __tablename__ = 'applications'

    id = Column(Integer, primary_key=True)
    user = Column(String(256), nullable=False)
    collection = Column(String(256), nullable=False)
    #origin = Column(String(256), nullable=False)    # XXX do we need this
    last_modified = Column(Integer)
    data = Column(Text)


_GET_QUERY = """\
select
    last_modified, data
from
    applications
where
    user = :user
and
    collection = :collection
and
    last_modified >= :since
order by
    last_modified
"""


# XXX no bulk inserts in sqlite
_PUT_QUERY = """
insert into applications
    (user, collection, last_modified, data)
values
    (:user, :collection, :last_modified, :data)
"""


applications = Application.__table__
_TABLES.append(applications)


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
            table.metadata.bind = self.engine
            if options.get('create_tables', True):
                table.create(checkfirst=True)

    def _execute(self, *args, **kw):
        return safe_execute(self.engine, *args, **kw)

    def get_applications(self, user, collection, since=0):

        since = int(round_time(since) * 100)
        apps = self._execute(_GET_QUERY, user=user, collection=collection,
                             since=since)

        # XXX dumb: serialize/unserialize round trip for nothing
        return [json.loads(app.data) for app in apps]

    def add_applications(self, user, collection, applications):

        now = int(round_time() * 100)

        # the *real* storage will do bulk inserts of course
        for app in applications:
            self._execute(_PUT_QUERY, user=user, collection=collection,
                          last_modified=now, data=json.dumps(app))
