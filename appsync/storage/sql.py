import traceback

import simplejson as json
from sqlalchemy.exc import OperationalError, TimeoutError
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base, Column
from sqlalchemy import Integer, String, Text
from sqlalchemy.sql.expression import text

from zope.interface import implements

import vep

from mozsvc.exceptions import BackendError
from mozsvc.util import round_time, maybe_resolve_name

from appsync import logger
from appsync.storage import queries
from appsync.storage import (IAppSyncDatabase, CollectionDeletedError,
                             StorageAuthError)


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
    origin = Column(String(256), nullable=False)
    last_modified = Column(Integer, nullable=False)
    data = Column(Text)
    ## FIXME: user+collection+origin should/could be unique

applications = Application.__table__
_TABLES.append(applications)


class Collection(_Base):
    __tablename__ = 'collections'
    id = Column(Integer, primary_key=True)
    uuid = Column(String(256), nullable=False)
    user = Column(String(256), nullable=False)
    collection = Column(String(256), nullable=False)


collections = Collection.__table__
_TABLES.append(collections)


def _key(*args):
    return ':::'.join(args)


def execute_retry(engine, *args, **kwargs):
    try:
        return engine.execute(*args, **kwargs)
    except (OperationalError, TimeoutError), exc:
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
    implements(IAppSyncDatabase)

    def __init__(self, **options):
        verifier = options.pop("verifier", None)
        if verifier is None:
            verifier = vep.RemoteVerifier()
        else:
            verifier = maybe_resolve_name(verifier)
            if callable(verifier):
                verifier = verifier()
        self._verifier = verifier

        #sqlkw = {'pool_size': int(options.get('pool_size', 1)),
        #         'pool_recycle': int(options.get('pool_recycle', 3600)),
        #         'logging_name': 'appsync'}
        sqlkw = {}

        self.engine = create_engine(options['sqluri'], **sqlkw)
        for table in _TABLES:
            table.metadata.bind = self.engine
            if options.get('create_tables', True):
                table.create(checkfirst=True)

    def _execute(self, expr, *args, **kw):
        return execute_retry(self.engine, text(expr), *args, **kw)

    def delete(self, user, collection, client_id, reason, token):
        self._execute(queries.DEL_QUERY, user=user, collection=collection)
        self._execute(queries.ADD_DEL, user=user, collection=collection,
                      reason=reason, client_id=client_id)
        self._execute(queries.DEL_UUID, user=user, collection=collection)

    def get_uuid(self, user, collection, token):
        res = self._execute(queries.GET_UUID, user=user, collection=collection)
        res = res.fetchone()
        if res is None:
            return None
        return res.uuid

    def get_applications(self, user, collection, since, token):
        res = self._execute(queries.IS_DEL, user=user, collection=collection)
        deleted = res.fetchone()
        if deleted is not None:
            raise CollectionDeletedError(deleted.client_id, deleted.reason)

        since = int(round_time(since) * 100)
        apps = self._execute(queries.GET_QUERY, user=user,
                             collection=collection, since=since)

        # XXX dumb: serialize/unserialize round trip for nothing
        return [(round_time(app.last_modified / 100.),
                 json.loads(app.data)) for app in apps]

    def add_applications(self, user, collection, applications, token):
        res = self._execute(queries.IS_DEL, user=user, collection=collection)
        deleted = res.fetchone()
        res.close()
        if deleted is not None:
            self._execute(queries.REMOVE_DEL, user=user, collection=collection)

        now = int(round_time() * 100)

        # let's see if we have an uuid
        res = self._execute(queries.GET_UUID, user=user,
                            collection=collection)
        res = res.fetchone()
        if res is None:
            # we need to create one
            uuid = '%s-%s' % (now, collection)
            self._execute(queries.ADD_UUID, user=user,
                          collection=collection, uuid=uuid)
        else:
            uuid = res.uuid

        # the *real* storage will do bulk inserts of course
        for app in applications:
            origin = app['origin']
            res = self._execute(queries.GET_BY_ORIGIN_QUERY, user=user,
                                collection=collection, origin=origin)
            res = res.fetchone()
            if res is None:
                self._execute(queries.PUT_QUERY, user=user,
                              collection=collection,
                              last_modified=now, data=json.dumps(app),
                              origin=app['origin'])
            else:
                ## FIXME: for debugging
                if res.data == json.dumps(app):
                    ## This is a logic error on the client:
                    logger.error(('Bad attempt to update an application '
                                  ' to overwrite itself: %r') % app['origin'])

                self._execute(queries.UPDATE_BY_ORIGIN_QUERY, user=user,
                              collection=collection,
                              id=res.id, data=json.dumps(app),
                              last_modified=now)

    def get_last_modified(self, user, collection, token):
        res = self._execute(queries.LAST_MODIFIED, user=user,
                            collection=collection)
        res = res.fetchone()
        if res in (None, (None,)):
            return None
        # last modified is a timestamp * 100
        return round_time(res.last_modified / 100.)

    def verify(self, assertion, audience):
        """Authenticate then return a token"""
        try:
            email = self._verifier.verify(assertion, audience)["email"]
        except (ValueError, vep.TrustError):
            raise StorageAuthError
        token = 'CREATE A TOKEN HERE XXX'
        return email, token
