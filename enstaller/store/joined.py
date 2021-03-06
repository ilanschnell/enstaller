from base import AbstractStore


class JoinedStore(AbstractStore):

    def __init__(self, repos):
        self.repos = repos

    def connect(self, auth=None):
        for repo in self.repos:
            repo.connect(auth)

    def info(self):
        pass

    def where_from(self, key):
        for repo in self.repos:
            if repo.exists(key):
                return repo
        return None

    def get(self, key):
        for repo in self.repos:
            if repo.exists(key):
                return repo.get(key)
        raise KeyError

    def get_data(self, key):
        for repo in self.repos:
            if repo.exists(key):
                return repo.get_data(key)
        raise KeyError

    def get_metadata(self, key):
        for repo in self.repos:
            if repo.exists(key):
                return repo.get_metadata(key)
        raise KeyError

    def exists(self, key):
        for repo in self.repos:
            if repo.exists(key):
                return True
        return False

    def query(self, **kwargs):
        index = {}
        for repo in reversed(self.repos):
            index.update(repo.query(**kwargs))
        return index.iteritems()
