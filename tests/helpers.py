from kb.nextcloud_client import NextcloudError, RemoteEntry


def entry(path: str, file_id: str, etag: str = '"e"', is_dir: bool = False) -> RemoteEntry:
    return RemoteEntry(path=path, name=path.rsplit("/", 1)[-1], is_dir=is_dir, file_id=file_id,
                       size=None, modified=None, etag=etag, content_type=None, permissions=None)


class FakeClient:
    """A stand-in for NextcloudClient: maps a folder path to the entries inside it."""

    def __init__(self, tree: dict):
        self.tree = tree

    def list_folder(self, path: str = ""):
        if path not in self.tree:
            raise NextcloudError("Path not found (404).")
        return self.tree[path]