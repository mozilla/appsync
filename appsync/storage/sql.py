import traceback

import simplejson as json
from sqlalchemy.exc import OperationalError, TimeoutError
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base, Column
from sqlalchemy import Integer, String, Text

from mozsvc.exceptions import BackendError
from mozsvc.util import round_time

from appsync import logger
from appsync.storage import CollectionDeletedError


_TABLES = []
_Base = declarative_base()


class Deleted(_Base):
    __tablename__ = 'deleted'

    id = Column(Integer, primary_key=True)
    user = Column(String(256), nullable=False)
    collection = Column(String(256), nullable=False)
    reason = Column(String(256), nullable=False)
    client_id = Column(String(256), nullable=False)


deleted = Deleted.__table__
_TABLES.append(deleted)


class Application(_Base):
    __tablename__ = 'applications'

    id = Column(Integer, primary_key=True)
    user = Column(String(256), nullable=False)
    collection = Column(String(256), nullable=False)
    #origin = Column(String(256), nullable=False)    # XXX do we need this
    last_modified = Column(Integer)
    data = Column(Text)


applications = Application.__table__
_TABLES.append(applications)


_ADD_DEL = """
insert into deleted
    (user, collection, reason, client_id)
values
    (:user, :collection, :reason, :client_id)
"""


_REMOVE_DEL = """
delete from
    delete
where
    user = :user
and
    collection = :collection
"""

_IS_DEL = """
select
    client_id, reason
from
    deleted
where
    user = :user
and
    collection = :collection
"""


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

_DEL_QUERY = """
delete from
    applications
where
    user = :user
and
    collection = :collection
"""


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

    def delete(self, user, collection, client_id, reason=''):
        self._execute(_DEL_QUERY, user=user, collection=collection)
        self._execute(_ADD_DEL, user=user, collection=collection,
                      reason=reason, client_id=client_id)

    def get_applications(self, user, collection, since=0):
        res = self._execute(_IS_DEL, user=user, collection=collection)
        deleted = res.fetchone()
        if deleted is not None:
            raise CollectionDeletedError(deleted.client_id, deleted.reason)

        since = int(round_time(since) * 100)
        apps = self._execute(_GET_QUERY, user=user, collection=collection,
                             since=since)

        # XXX dumb: serialize/unserialize round trip for nothing
        return [json.loads(app.data) for app in apps]

    def add_applications(self, user, collection, applications):
        res = self._execute(_IS_DEL, user=user, collection=collection)
        deleted = res.fetchone()
        if deleted is not None:
            self._execute(_REMOVE_DEL, user=user, collection=collection)

        now = int(round_time() * 100)

        # the *real* storage will do bulk inserts of course
        for app in applications:
            self._execute(_PUT_QUERY, user=user, collection=collection,
                          last_modified=now, data=json.dumps(app))
