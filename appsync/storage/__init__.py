
from zope.interface import Interface


class CollectionDeletedError(Exception):
    """Error raised when accessing a collection that has been deleted."""
    def __init__(self, client_id, reason):
        self.client_id = client_id
        self.reason = reason
        super(CollectionDeletedError, self).__init__()


class EditConflictError(Exception):
    """Error raised when conflicting edits are detected."""
    pass


class StorageAuthError(Exception):
    """Error when a auth issue happens"""
    pass


class ConnectionError(Exception):
    """Error when a connection error occurs"""
    pass


class IAppSyncDatabase(Interface):
    """Interface definition for AppSync database backends.

    This class defines the abstract interface that must be implemented by
    AppSync storage backends.  It is designed to allow tunnelling of the
    user's credentials through to the backend for authentication and
    auditing purposes.

    Before accessing any data stored in the database, you must provide valid
    user credentials to the verify() method.  This will return an access token
    which can be used when calling other database methods.
    """

    def verify(assertion, audience):
        """Authenticate the user and return an access token.

        This method uses the given BrowserID assertion to authenticate to
        the database and begin an access session.  If authentication is
        successful it will return the user's email address and an access
        token for the database.  If authentication fails it returns None
        and the JSON error response from the server.
        """

    def get_last_modified(user, collection, token):
        """Get the latest last-modified time for any app in the collection.

        This method returns the latest timestamp at which any application in
        the specified collection was modified.  You can think of this as
        being the last-modified time of the collection as a whole.
        """

    def delete(user, collection, client_id, reason, token):
        """Delete a collection.

        This method marks the specified collection as deleted, recording the
        client_id and reason for future reference.
        """

    def get_uuid(user, collection, token):
        """Get the UUID identifying a collection.

        This method returns an automatically-generated UUID that uniquely
        identifies the specified collection.  UUIDs are assigned internally
        by the storage backend and cannot be changed.

        If the specified collection does not exist or has been deleted then
        None is returned.
        """

    def get_applications(user, collection, since, token):
        """Get all applications that have been modified later than 'since'.

        This method returns a list of all applications from the specified
        collection that have been modified later than time 'since'.  It
        may return multiple entries per application and they need not be in
        any particular order.
        """

    def add_applications(user, collection, applications, token):
        """Add application updates to a collection.

        This method stores the given list of applications into the specified
        collection.  They will be marked as modified as of the current server
        time, which is returned.
        """
