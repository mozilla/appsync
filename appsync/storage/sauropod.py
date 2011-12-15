import uuid
import functools
import simplejson as json

from zope.interface import implements

from mozsvc.util import round_time

import pysauropod

from appsync import logger
from appsync.cache import Cache, CacheError
from appsync.storage import IAppSyncDatabase
from appsync.util import urlb64decode
from appsync.storage import (CollectionDeletedError, EditConflictError,
                             StorageAuthError, ConnectionError, ServerError)


def convert_sauropod_errors(func):
    """Method wrapper to convert sauropod errors into appsync errors."""
    @functools.wraps(func)
    def wrapper(*args, **kwds):
        try:
            return func(*args, **kwds)
        except pysauropod.ConflictError:
            raise EditConflictError
        except pysauropod.AuthenticationError:
            raise StorageAuthError
        except pysauropod.ConnectionError:
            raise ConnectionError
        except pysauropod.ServerError:
            raise ServerError
    return wrapper


def _key(*args):
    key = ':::'.join(args)
    return str(key)


class SauropodDatabase(object):
    """AppSync storage engine built on the preliminary Sauropod API.

    This class stores AppSync data in Sauropod.  Data for each application
    is stored under a key named:

        <collection>::item::<id>

    The contents of this key are simply the JSON object describing the app.
    There is also a metadata document for each collection, stored at:

        <collection>::meta

    The metadata document contains the uuid and last-modified time for the
    collection, a list of installed apps sorted by their modification time,
    and a map giving the last-known etag for each app:

        {
         "uuid": <uuid>,

         "last_modified": <timestamp>,

         "apps": [
            [<timestamp>, <appid>],
            [<timestamp>, <appid>],
            ...
         ],

         "etags": {
            <appid>: <etag>,
            <appid>: <etag>,
         }
        }

    The metadata document also serves as a marker for collections that have
    been deleted, by storing the clientid and reason for future reference.

    Checking for updates involves reading the metadata document, consulting the
    index therein, and fetching any applications with modification time newer
    than the requested value.

    Writing updates is a little more complicated since it needs to update
    the metadata document while avoiding conflicts with concurrent updates:

        1)  Read the metadata document.  If the client doesn't have all
            updates contained therein, fail with a conflict error.

        2)  Write out each update to its respective app key, using the etag
            from the metadata document to avoid conflicts.  If an update
            fails because the app key differs from the metadata document,
            repair the metadata document then fail with a conflict error.

        3)  Construct the updated metadata document and conditionally write
            it back to the store.  If this fails due to concurrent edits,
            fail with a conflict error.

    By failing with a conflict error when it detects an out-of-date metadata
    document, this process ensures that no updates will be lost due to
    concurrent writes of the same application.  By repairing the metadata
    document it ensures that the system can recover from updates that
    died halfway through.
    """
    implements(IAppSyncDatabase)

    def __init__(self, store_url, appid, **kwds):
        cache_activated = kwds.pop('cache_activated', False)
        if cache_activated:
            cache_options = {'servers': kwds.pop('cache_servers', '127.0.0.1'),
                             'prefix': kwds.pop('cache_prefix',
                                                'appsyncsauropod')}
            self.cache_ttl = kwds.pop('cache_ttl', 300)
            self.cache = Cache(**cache_options)
        else:
            self.cache = self.cache_ttl = None
        self._store = pysauropod.connect(store_url, appid, **kwds)
        self.authentication = True

    def set_authentication(self, state):
        if not state:
            raise ValueError("The Sauropod backend cannot work without tokens")

    @convert_sauropod_errors
    def verify(self, assertion, audience):
        """Authenticate the user and return an access token."""
        userid = self._get_userid_from_assertion(assertion)
        credentials = {"assertion": assertion, "audience": audience}
        session = self._store.start_session(userid, credentials)
        return session.userid, "%s:%s" % (session.userid, session.sessionid)

    def _get_userid_from_assertion(self, assertion):
        """Extract the userid from a BrowserID assertion."""
        try:
            data = json.loads(urlb64decode(assertion))
        except (ValueError, TypeError):
            return assertion
        else:
            payload = data["certificates"][0].split(".")[1]
            payload = json.loads(urlb64decode(payload))
            return payload["principal"]["email"]

    def _resume_session(self, token):
        """Resume the Sauropod session encoded in the given token."""
        try:
            userid, sessionid = token.split(":", 1)
        except ValueError:
            # the token is corrupted, somehow
            raise pysauropod.AuthenticationError('Corrupted token')

        return self._store.resume_session(userid, sessionid)

    #
    # cache managment
    #
    def _purge_cache(self, user, collection):
        if self.cache is None:
            return
        cache_key = _key(user, collection, 'meta')
        try:
            self.cache.delete(cache_key)
        except CacheError:
            logger.error('Unable to delete a cache entry')

    def _set_cached_metadata(self, session, user, collection, data, etag):
        key = collection + "::meta"
        doc = session.set(key, json.dumps(data), if_match=etag)

        if self.cache is not None:
            cache_key = _key(user, collection, 'meta')
            try:
                self.cache.set(cache_key, doc, self.cache_ttl)
            except CacheError:
                logger.error('Unable to read the metadata in the cache.')

    def _get_cached_metadata(self, session, user, collection):
        # getting the cached value if possible
        if self.cache is not None:
            cache_key = _key(user, collection, 'meta')
            try:
                cached = self.cache.get(cache_key)
            except CacheError:
                logger.error('Unable to read the metadata in the cache.')
                cached = None

            if cached is not None:
                return cached

        # getting the meta document.
        doc = session.getitem(collection + "::meta")

        # set the cache
        if self.cache is not None:
            try:
                self.cache.set(cache_key, doc, time=self.cache_ttl)
            except CacheError:
                logger.error('Was unable to cache the metadata.')

        return doc

    @convert_sauropod_errors
    def get_last_modified(self, user, collection, token):
        """Get the latest last-modified time for any app in the collection."""
        s = self._resume_session(token)

        # To get the last-modified time we need only read the meta document.
        try:
            item = self._get_cached_metadata(s, user, collection)
            meta = json.loads(item.value)
        except KeyError:
            return 0
        if meta.get("deleted", False):
            raise CollectionDeletedError(meta.get("client_id", ""),
                                         meta.get("reason", ""))
        return round_time(meta.get("last_modified", 0))

    @convert_sauropod_errors
    def delete(self, user, collection, client_id, reason, token):
        s = self._resume_session(token)
        # Grab the collection metadata as it is before deleting anything.
        # We can bail out early if it's already deleted.
        try:
            meta = self._get_cached_metadata(s, user, collection)
        except KeyError:
            meta_etag = ""
            meta_data = {}
        else:
            meta_etag = meta.etag
            meta_data = json.loads(meta.value)
        if meta_data.get("deleted", False):
            return
        etags = meta_data.get("etags", {})
        # Update the metadata to mark it as deleted.
        # We do this first to minimize the impact of conflicts with
        # concurrent updates, by not deleting apps that some clients
        # might think are still in place.
        meta_data["deleted"] = True
        meta_data["client_id"] = client_id
        meta_data["reason"] = reason
        meta_data["apps"] = []
        meta_data["etags"] = {}
        meta_data["uuid"] = None
        meta_data["last_modified"] = round_time()
        self._set_cached_metadata(s, user, collection, meta_data, meta_etag)

        # Now we can delete the applications that were recorded in
        # the metadata.
        # If we're doing this concurrently with an upload, we might get
        # some edit conflicts here.  There's not much we can do except
        # bail out - the uploader will get an edit conflict when they go to
        # save the metadata document, and hopefully they'll clean up the mess.
        for appid, etag in etags.iteritems():
            key = "%s::item::%s" % (collection, appid)
            try:
                s.delete(key, if_match=etag)
            except KeyError:
                # Someone else has already delete it, no biggie.
                pass
            except pysauropod.ConflictError:
                # Someone has uploaded a new version; they can deal with it.
                pass
        # Done.  We might have left some dangling app records, but
        # that's not so bad in the scheme of things.

    @convert_sauropod_errors
    def get_uuid(self, user, collection, token):
        """Get the UUID identifying a collection."""
        s = self._resume_session(token)
        # To get the last-modified time we need only read the meta document.
        try:
            item = self._get_cached_metadata(s, user, collection)
            meta = json.loads(item.value)
        except KeyError:
            return None
        return meta.get("uuid", None)

    @convert_sauropod_errors
    def get_applications(self, user, collection, since, token):
        """Get all applications that have been modified later than 'since'."""
        s = self._resume_session(token)
        since = round_time(since)
        updates = []
        # Check the collection metadata first.
        # It might be deleted, or last_modified might be too early.
        # In either case, this lets us bail out before doing any hard work.
        try:
            item = self._get_cached_metadata(s, user, collection)
            meta = json.loads(item.value)
        except KeyError:
            return updates
        if meta.get("deleted", False):
            raise CollectionDeletedError(meta.get("client_id", ""),
                                         meta.get("reason", ""))
        last_modified = round_time(meta.get("last_modified", 0))
        if last_modified < since:
            return updates
        # Read and return all apps with modification time > since.
        apps = meta.get("apps", [])
        for (last_modified, appid) in apps:
            last_modified = round_time(last_modified)
            if last_modified <= since:
                break
            key = "%s::item::%s" % (collection, appid)
            try:
                app = json.loads(s.get(key))
            except KeyError, e:
                # It has been deleted; ignore it.
                continue
            updates.append((last_modified, app))
        return updates

    @convert_sauropod_errors
    def add_applications(self, user, collection, applications, token):
        """Add application updates to a collection."""
        s = self._resume_session(token)
        # Load the current metadata state so we can update it when finished.
        # We need it first so we can detect conflicts from concurrent uploads.
        try:
            meta = self._get_cached_metadata(s, user, collection)
        except KeyError:
            meta_etag = ""
            meta_data = {}
        else:
            meta_etag = meta.etag
            meta_data = json.loads(meta.value)
        apps = meta_data.get("apps", [])
        etags = meta_data.get("etags", {})
        # Generate a new last_modified timestamp, and make sure it's
        # actually larger than any existing timestamp. Yay clock skew!
        now = round_time()
        last_modified = round_time(meta_data.get("last_modified", 0))
        if now <= last_modified:
            now = last_modified + 1
        # Store the data for each application.
        # We use the stored etags to verify the the application hasn't
        # already been updated.  If it has been, we get the updated etag
        # so that we can repair the metadata document.
        has_conflict = False
        for app in applications:
            appid = app["origin"]
            etag = etags.get(appid, "")
            key = "%s::item::%s" % (collection, appid)
            value = json.dumps(app)
            try:
                item = s.set(key, value, if_match=etag)
            except pysauropod.ConflictError:
                # Someone else has changed that key.
                # If we're lucky, it was us in a previous failed write attempt.
                # Otherwise, we're going to need to report a conflict.
                try:
                    item = s.getitem(key)
                except KeyError:
                    has_conflict = True
                    etags[appid] = ""
                else:
                    etags[appid] = item.etag
                    if item.value != value:
                        has_conflict = True
            else:
                etags[appid] = item.etag
            # Update the app's modification time in the index list.
            # We'll re-sort the list once at the end.
            for i, item in enumerate(apps):
                if item[1] == appid:
                    apps[i] = [now, appid]
                    break
            else:
                apps.append([now, appid])
        # Update the metadata document.
        # Hopefully no-one else has written it in the meantime.
        # If we get a conflict, we leave all of our modifications in place.
        # The client will just try again later and happily find that all
        # of the keys have already been updated.
        apps.sort(reverse=True)
        meta_data["apps"] = apps
        meta_data["etags"] = etags
        if meta_data.pop("deleted", False):
            meta_data.pop("client_id", None)
            meta_data.pop("reason", None)
        meta_data["last_modified"] = now
        if not meta_data.get("uuid"):
            meta_data["uuid"] = uuid.uuid4().hex

        self._set_cached_metadata(s, user, collection, meta_data, meta_etag)

        # Finally, we have completed the writes.
        # Report back if we found some apps that had been changed and
        # could not be overwritten.
        if has_conflict:
            raise EditConflictError()
        return now
