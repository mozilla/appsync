

class CollectionDeletedError(Exception):

    def __init__(self, client_id, reason):
        self.client_id = client_id
        self.reason = reason
        super(CollectionDeletedError, self).__init__()
