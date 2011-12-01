from mozsvc.util import resolve_name
from zope.interface import implements
from appsync.storage import IAppSyncDatabase


class MirroredDatabase(object):
    implements(IAppSyncDatabase)

    def __init__(self, **options):
        self._readwrite = self._backend('readwrite', options)
        self._write = self._backend('write', options)

    def _backend(self, name, options):
        klass = resolve_name(options[name])
        klass_options = {}
        for key, value in options.items():
            if not key.startswith(name + '.'):
                continue
            key = key.split('.', 1)[-1]
            klass_options[key] = value

        return klass(**klass_options)

    def delete(self, *args, **kw):
        self._readwrite.delete(*args, **kw)
        self._write.delete(*args, **kw)

    def get_uuid(self, *args, **kw):
        return self._readwrite.get_uuid(*args, **kw)

    def get_applications(self, *args, **kw):
        return self._readwrite.get_applications(*args, **kw)

    def add_applications(self, *args, **kw):
        self._readwrite.add_applications(*args, **kw)
        self._write.add_applications(*args, **kw)

    def get_last_modified(self, *args, **kw):
        return self._readwrite.get_last_modified(*args, **kw)

    def verify(self, *args, **kw):
        return self._readwrite.verify(*args, **kw)
