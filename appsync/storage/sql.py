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

from appsync.cache import Cache   # XXX should use it via plugin conf.
from appsync import logger
from appsync.storage import queries
from appsync.storage import (IAppSyncDatabase, CollectionDeletedError,
                             StorageAuthError)
from appsync.util import gen_uuid


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

        self.session_ttl = int(options.get('session_ttl', '300'))
        cache_options = {'servers': options.get('cache_servers', '127.0.0.1'),
                         'prefix': options.get('cache_prefix', 'appsyncsql')}

        self.cache = Cache(**cache_options)
        self.authentication = bool(options.get('authentication', True))

    def _execute(self, expr, *args, **kw):
        return execute_retry(self.engine, text(expr), *args, **kw)

    def delete(self, user, collection, client_id, reason, token):
        self._check_token(token)
        self._execute(queries.DEL_QUERY, user=user, collection=collection)
        self._execute(queries.ADD_DEL, user=user, collection=collection,
                      reason=reason, client_id=client_id)
        self._execute(queries.DEL_UUID, user=user, collection=collection)

    def get_uuid(self, user, collection, token):
        self._check_token(token)
        res = self._execute(queries.GET_UUID, user=user, collection=collection)
        res = res.fetchone()
        if res is None:
            return None
        return res.uuid

    def get_applications(self, user, collection, since, token):
        self._check_token(token)
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
        self._check_token(token)
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
        self._check_token(token)
        res = self._execute(queries.LAST_MODIFIED, user=user,
                            collection=collection)
        res = res.fetchone()
        if res in (None, (None,)):
            return None
        # last modified is a timestamp * 100
        return round_time(res.last_modified / 100.)

    def verify(self, assertion, audience):
        """Authenticate then return a token"""
        if not self.authentication:
            raise NotImplementedError('authentication not activated')

        try:
            email = self._verifier.verify(assertion, audience)["email"]
        except (ValueError, vep.TrustError), e:
            raise StorageAuthError(e.message)

        # create the token and create a session with it
        token = gen_uuid(email, audience)
        self.cache.set(token, (email, audience), time=self.session_ttl)
        return email, token

    def _check_token(self, token):
        if not self.authentication:
            # bypass authentication
            return

        # XXX do we want to check that the user owns that path ?
        res = self.cache.get(token)
        if res is None:
            raise StorageAuthError()
