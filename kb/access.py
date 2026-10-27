"""Ask Nextcloud what a given user may see. Nextcloud decides, we never guess."""
from dataclasses import dataclass

from kb.config import NextcloudSettings, load_nextcloud_settings
from kb.nextcloud_client import NextcloudClient, NextcloudError

PROJECTS_ROOT = "Projects/"


@dataclass
class UserContext:
    username: str
    client: NextcloudClient      # acts as this user
    service: NextcloudClient     # kb_service: server-side only, never shown to users
    projects: list[str]          # projects this user could see at login
    base_url: str


def project_of(path: str) -> str:
    parts = path.split("/")
    return parts[1] if len(parts) > 2 and parts[0] == "Projects" else ""


def authenticate(base_url: str, username: str, app_password: str) -> NextcloudClient | None:
    """A client acting as this user, or None if the login is wrong."""
    client = NextcloudClient(NextcloudSettings(base_url, username, app_password))
    try:
        client.list_folder("")
    except NextcloudError as exc:
        if "401" in str(exc):
            return None
        raise
    return client


def allowed_projects(user_client: NextcloudClient, service_client: NextcloudClient) -> list[str]:
    """Projects whose folder in the user's own view has the SAME Nextcloud file ID as the real one.

    Comparing IDs, not just names, stops a user from creating their own folder called Project_B.
    """
    real = {e.name: e.file_id for e in service_client.list_folder("Projects") if e.is_dir}
    mine = {e.name: e.file_id for e in user_client.list_folder("") if e.is_dir}
    return sorted(name for name, fid in real.items() if mine.get(name) == fid)


def can_read(user_client: NextcloudClient, kb_path: str, file_id: str | None = None) -> bool:
    """True only if Nextcloud shows this user that exact file right now. Any doubt means no."""
    if not kb_path.startswith(PROJECTS_ROOT):
        return False
    parent, _, name = kb_path.removeprefix(PROJECTS_ROOT).rpartition("/")
    try:
        entries = user_client.list_folder(parent)
    except NextcloudError:
        return False
    for e in entries:
        if e.name == name:
            return file_id is None or e.file_id == file_id
    return False


def login(username: str, app_password: str) -> UserContext | None:
    settings = load_nextcloud_settings()
    client = authenticate(settings.base_url, username, app_password)
    if client is None:
        return None
    service = NextcloudClient(settings)
    return UserContext(username, client, service, allowed_projects(client, service), settings.base_url)