import unittest

from zope.interface.verify import verifyClass

from appsync.storage import IAppSyncDatabase


class TestDatabaseInterfaces(unittest.TestCase):

    def test_sql_backend(self):
        from appsync.storage.sql import SQLDatabase
        verifyClass(IAppSyncDatabase, SQLDatabase)

    def test_sauropod_backend(self):
        from appsync.storage.sauropod import SauropodDatabase
        verifyClass(IAppSyncDatabase, SauropodDatabase)
