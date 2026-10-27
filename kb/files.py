"""Exact file and folder search. Nextcloud is the source of truth, so we ask it every time."""
from kb.nextcloud_client import NextcloudClient, RemoteEntry

ROOT = "Projects"


def list_all(client: NextcloudClient, root: str = ROOT) -> list[RemoteEntry]:
    """Every file under root, found by walking the folders."""
    files, stack = [], [root]
    while stack:
        for e in client.list_folder(stack.pop()):
            if e.is_dir:
                stack.append(e.path)
            else:
                files.append(e)
    return sorted(files, key=lambda e: e.path)


def _project(entry: RemoteEntry) -> str:
    parts = entry.path.split("/")
    return parts[1] if len(parts) > 2 else ""


def find_files(client: NextcloudClient, name: str, project: str | None = None) -> list[RemoteEntry]:
    """Exact filename matches first, then partial matches. Case-insensitive."""
    query = name.lower()
    ranked = []
    for e in list_all(client):
        if project and _project(e).lower() != project.lower():
            continue
        filename = e.name.lower()
        if filename == query:
            ranked.append((0, e.path, e))
        elif query in filename:
            ranked.append((1, e.path, e))
    return [e for _, _, e in sorted(ranked, key=lambda t: (t[0], t[1]))]


def browse(client: NextcloudClient, path: str = ROOT) -> list[RemoteEntry]:
    """Folders first, then files, for one folder."""
    return sorted(client.list_folder(path), key=lambda e: (not e.is_dir, e.name.lower()))