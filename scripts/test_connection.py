import sys

from kb.config import load_nextcloud_settings
from kb.nextcloud_client import NextcloudClient


def main() -> None:
    folder = sys.argv[1] if len(sys.argv) > 1 else ""
    client = NextcloudClient(load_nextcloud_settings())
    print(f"Contents of '/{folder}':")
    for e in client.list_folder(folder):
        kind = "DIR " if e.is_dir else "FILE"
        print(f"  {kind} id={e.file_id} size={e.size} path={e.path}")


if __name__ == "__main__":
    main()