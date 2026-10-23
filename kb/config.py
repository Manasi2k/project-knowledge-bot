import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class NextcloudSettings:
    base_url: str
    username: str
    app_password: str


def _require(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def load_nextcloud_settings() -> NextcloudSettings:
    return NextcloudSettings(
        base_url=_require("NEXTCLOUD_URL").rstrip("/"),
        username=_require("NEXTCLOUD_USERNAME"),
        app_password=_require("NEXTCLOUD_APP_PASSWORD"),
    )