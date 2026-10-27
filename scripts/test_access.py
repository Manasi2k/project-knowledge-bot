import os
import sys

from kb.access import allowed_projects, authenticate, can_read
from kb.config import load_nextcloud_settings
from kb.nextcloud_client import NextcloudClient

PROBES = [
    "Projects/Project_A/Technical_Documents/Architecture.pdf",
    "Projects/Project_B/Technical_Documents/Architecture.pdf",
    "Projects/Project_C/Technical_Documents/Authentication_Guide.pdf",
    "Projects/Project_B/Data/Project_Metrics.xlsx",
    "Projects/Project_A/Does_Not_Exist.pdf",
]

settings = load_nextcloud_settings()
service = NextcloudClient(settings)
user = sys.argv[1]
client = authenticate(settings.base_url, user, os.getenv(f"{user.upper()}_APP_PASSWORD", ""))
if client is None:
    sys.exit(f"Login failed for {user}")

print(f"{user} can see projects: {allowed_projects(client, service)}")
service_ids = {e.name: e.file_id for e in service.list_folder("Projects")}
for e in client.list_folder(""):
    if e.name in service_ids:
        print(f"  folder {e.name}: id as {user} = {e.file_id}, id as service = {service_ids[e.name]}")
for path in PROBES:
    print(f"  {'ALLOW' if can_read(client, path) else 'DENY '}  {path}")