import xml.etree.ElementTree as ET
from dataclasses import dataclass
from typing import Optional
from urllib.parse import quote, unquote, urlparse

import requests

from kb.config import NextcloudSettings

NS = {"d": "DAV:", "oc": "http://owncloud.org/ns", "nc": "http://nextcloud.org/ns"}

PROPFIND_BODY = """<?xml version="1.0"?>
<d:propfind xmlns:d="DAV:" xmlns:oc="http://owncloud.org/ns" xmlns:nc="http://nextcloud.org/ns">
  <d:prop>
    <d:getlastmodified/>
    <d:getcontentlength/>
    <d:getcontenttype/>
    <d:getetag/>
    <d:resourcetype/>
    <oc:fileid/>
    <oc:permissions/>
  </d:prop>
</d:propfind>"""


class NextcloudError(Exception):
    """Raised for any failed Nextcloud request."""


@dataclass(frozen=True)
class RemoteEntry:
    path: str
    name: str
    is_dir: bool
    file_id: Optional[str]
    size: Optional[int]
    modified: Optional[str]
    etag: Optional[str]
    content_type: Optional[str]
    permissions: Optional[str]


class NextcloudClient:
    def __init__(self, settings: NextcloudSettings) -> None:
        self._files_root = f"{settings.base_url}/remote.php/dav/files/{quote(settings.username)}"
        self._root_path = urlparse(self._files_root).path
        self._session = requests.Session()
        self._session.auth = (settings.username, settings.app_password)

    def _url(self, path: str) -> str:
        clean = path.strip("/")
        return f"{self._files_root}/{quote(clean, safe='/')}" if clean else f"{self._files_root}/"

    def _check(self, resp: requests.Response, ok: tuple[int, ...]) -> None:
        if resp.status_code in ok:
            return
        if resp.status_code == 401:
            raise NextcloudError("Authentication failed (401). Check username and app password.")
        if resp.status_code == 404:
            raise NextcloudError("Path not found (404).")
        raise NextcloudError(f"Unexpected status {resp.status_code}: {resp.text[:200]}")

    @staticmethod
    def _ok_props(response: ET.Element) -> Optional[ET.Element]:
        for propstat in response.findall("d:propstat", NS):
            if "200" in (propstat.findtext("d:status", namespaces=NS) or ""):
                return propstat.find("d:prop", NS)
        return None

    def list_folder(self, path: str = "") -> list[RemoteEntry]:
        """List the direct children of a folder (WebDAV Depth: 1)."""
        resp = self._session.request(
            "PROPFIND", self._url(path), data=PROPFIND_BODY,
            headers={"Depth": "1", "Content-Type": "application/xml"}, timeout=30,
        )
        self._check(resp, ok=(207,))
        requested = path.strip("/")
        entries: list[RemoteEntry] = []
        for response in ET.fromstring(resp.content).findall("d:response", NS):
            href = unquote(response.findtext("d:href", namespaces=NS) or "")
            rel = href[len(self._root_path):].strip("/")
            if rel == requested:  # the folder itself is echoed back
                continue
            prop = self._ok_props(response)
            if prop is None:
                continue
            size = prop.findtext("d:getcontentlength", namespaces=NS)
            entries.append(RemoteEntry(
                path=rel,
                name=rel.rsplit("/", 1)[-1],
                is_dir=prop.find("d:resourcetype/d:collection", NS) is not None,
                file_id=prop.findtext("oc:fileid", namespaces=NS),
                size=int(size) if size else None,
                modified=prop.findtext("d:getlastmodified", namespaces=NS),
                etag=prop.findtext("d:getetag", namespaces=NS),
                content_type=prop.findtext("d:getcontenttype", namespaces=NS),
                permissions=prop.findtext("oc:permissions", namespaces=NS),
            ))
        return entries
    
    def download(self, path: str) -> bytes:
        resp = self._session.get(self._url(path), timeout=60)
        self._check(resp, ok=(200,))
        return resp.content        