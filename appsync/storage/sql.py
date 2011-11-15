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
from appsync.storage.queries import *


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
        return execute_retry(self.engine, *args, **kw)

    def delete(self, user, collection, client_id, reason, token):
        self._execute(DEL_QUERY, user=user, collection=collection)
        self._execute(ADD_DEL, user=user, collection=collection,
                      reason=reason, client_id=client_id)
        self._execute(DEL_UUID, user=user, collection=collection)

    def get_uuid(self, user, collection, token):
        res = self._execute(GET_UUID, user=user, collection=collection)
        res = res.fetchone()
        if res is None:
            return None
        return res.uuid

    def get_applications(self, user, collection, since, token):
        res = self._execute(IS_DEL, user=user, collection=collection)
        deleted = res.fetchone()
        if deleted is not None:
            raise CollectionDeletedError(deleted.client_id, deleted.reason)

        since = int(round_time(since) * 100)
        apps = self._execute(GET_QUERY, user=user, collection=collection,
                             since=since)

        # XXX dumb: serialize/unserialize round trip for nothing
        return [json.loads(app.data) for app in apps]

    def add_applications(self, user, collection, applications, token):
        res = self._execute(IS_DEL, user=user, collection=collection)
        deleted = res.fetchone()
        res.close()
        if deleted is not None:
            self._execute(REMOVE_DEL, user=user, collection=collection)

        now = int(round_time() * 100)

        # let's see if we have an uuid
        res = self._execute(GET_UUID, user=user,
                            collection=collection)
        res = res.fetchone()
        if res is None:
            # we need to create one
            uuid = '%s-%s' % (now, collection)
            self._execute(ADD_UUID, user=user,
                          collection=collection, uuid=uuid)
        else:
            uuid = res.uuid


        # the *real* storage will do bulk inserts of course
        for app in applications:
            self._execute(PUT_QUERY, user=user, collection=collection,
                          last_modified=now, data=json.dumps(app))

    def get_last_modified(self, user, collection, token):
        res = self._execute(LAST_MODIFIED, user=user, collection=collection)
        res = res.fetchone()
        if res is None:
            return None
        return res.last_modified

    def verify(self, assertion, audience):
        """Authenticate then return a token"""
        ## FIXME: basic HTTP errors should be caught and handled
        ## FIXME: browser certifications
        resp = urllib.urlopen(
            _BROWSERID_VERIFY,
            urllib.urlencode(dict(assertion=assertion, audience=audience)))
        resp_data = json.loads(resp.read())

        token = 'CREATE A TOKEN HERE XXX'
        if resp_data.get('email') and resp_data['status'] == _OK:
            return email, token

        return None
