from collections import Counter

from kb.config import load_nextcloud_settings
from kb.extraction import extract
from kb.nextcloud_client import NextcloudClient

client = NextcloudClient(load_nextcloud_settings())

files, stack = [], ["Projects"]
while stack:
    for e in client.list_folder(stack.pop()):
        if e.is_dir:
            stack.append(e.path)
        else:
            files.append(e)

counts = Counter()
for e in sorted(files, key=lambda e: e.path):
    res = extract(e.name, client.download(e.path))
    counts[res.status] += 1
    chars = sum(len(s.text) for s in res.segments)
    methods = ",".join(sorted({s.method for s in res.segments}))
    print(f"{res.status:8s} {len(res.segments):3d} seg {chars:6d} ch  {methods:9s} {e.path.removeprefix('Projects/')}")
    for note in res.notes + [x for x in (res.error, res.skipped) if x]:
        print(f"{'':10s}-> {note}")
print(f"\n{len(files)} files:", dict(counts))