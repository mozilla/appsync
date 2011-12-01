import os
import unittest
import time
import json

from webtest import TestApp
from webob import exc
from webob.dec import wsgify
from pyramid import testing
from mozsvc.config import load_into_settings

from appsync import CatchAuthError
from appsync.tests.test_server import TestSyncApp


_INI = os.path.join(os.path.dirname(__file__), 'test_mirror.ini')


class TestMirror(TestSyncApp):

    ini = _INI

    def tearDown(self):
        uris = ['storage.readwrite.sqluri', 'storage.write.sqluri']

        for uri in uris:
            sqluri = self.config.get_settings().get(uri)
            if sqluri is not None and sqluri.startswith('sqlite'):
                filename = sqluri[len('sqlite://'):]
                if os.path.exists(filename):
                    os.remove(filename)
