import shutil
from collections import Counter

from kb.chunking import chunk_file
from kb.config import load_nextcloud_settings
from kb.extraction import extract
from kb.nextcloud_client import NextcloudClient
from kb.vectorstore import PERSIST_DIR, get_store

shutil.rmtree(PERSIST_DIR, ignore_errors=True)   # full rebuild every run
store = get_store()
client = NextcloudClient(load_nextcloud_settings())

files, stack = [], ["Projects"]
while stack:
    for e in client.list_folder(stack.pop()):
        if e.is_dir:
            stack.append(e.path)
        else:
            files.append(e)

counts, total_chunks = Counter(), 0
for e in sorted(files, key=lambda e: e.path):
    res = extract(e.name, client.download(e.path))
    counts[res.status] += 1
    texts, metas, ids = chunk_file(e, res)
    if texts:
        store.add_texts(texts=texts, metadatas=metas, ids=ids)
    total_chunks += len(texts)
    print(f"{res.status:8s} {len(texts):3d} chunks  {e.path.removeprefix('Projects/')}")
    for note in res.notes + [x for x in (res.error, res.skipped) if x]:
        print(f"{'':10s}-> {note}")

print(f"\n{len(files)} files, {total_chunks} chunks:", dict(counts))