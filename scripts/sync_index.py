import argparse
import json
import time
from datetime import datetime, timezone

from kb.chunking import INDEX_VERSION, chunk_file
from kb.config import load_nextcloud_settings
from kb.extraction import extract
from kb.files import list_all
from kb.nextcloud_client import NextcloudClient
from kb.sync import indexed_state, plan_sync, split_known_failures
from kb.vectorstore import get_store

LOG_FILE = "sync_log.jsonl"          # never contains document text, only paths, statuses and counts
FAILURES_FILE = "sync_failures.json"  # files that produced nothing; skipped until they change
MAX_FILE_BYTES = 50 * 1024 * 1024     # larger files are skipped, not downloaded


def log(event: dict) -> None:
    event["time"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    with open(LOG_FILE, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(event) + "\n")


def load_failures() -> dict:
    try:
        with open(FAILURES_FILE, encoding="utf-8") as fh:
            return json.load(fh)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def save_failures(failures: dict) -> None:
    with open(FAILURES_FILE, "w", encoding="utf-8") as fh:
        json.dump(failures, fh, indent=1)


def download_with_retry(client: NextcloudClient, path: str, attempts: int = 3) -> bytes:
    for i in range(attempts):
        try:
            return client.download(path)
        except Exception:
            if i == attempts - 1:
                raise
            time.sleep(2 ** i)


def remove_file(store, file_id: str) -> int:
    ids = store.get(where={"file_id": file_id})["ids"]
    if ids:
        store.delete(ids=ids)
    return len(ids)


def run_once(dry_run: bool) -> None:
    client = NextcloudClient(load_nextcloud_settings())
    store = get_store()
    files = list_all(client)
    state = indexed_state(store)
    present = {e.file_id for e in files}
    failures = {fid: v for fid, v in load_failures().items() if fid in present}   # forget deleted files
    todo, deleted, unchanged = plan_sync(files, state, INDEX_VERSION)
    todo, known = split_known_failures(todo, failures, INDEX_VERSION)
    print(f"{len(files)} files in Nextcloud | unchanged {unchanged} | to index {len(todo)} | "
          f"to remove {len(deleted)} | known failures skipped {len(known)}")

    for fid in deleted:
        path = state[fid]["path"]
        print(f"  deleted   {path}")
        if not dry_run:
            log({"action": "deleted", "path": path, "chunks_removed": remove_file(store, fid)})
            failures.pop(fid, None)

    for e, reason in todo:
        print(f"  {reason:22s} {e.path}")
        if dry_run:
            continue
        marker = {"etag": e.etag or "", "path": e.path, "version": INDEX_VERSION}
        if e.size and e.size > MAX_FILE_BYTES:
            print(f"    SKIPPED: {e.size / 1_048_576:.0f} MB is over the {MAX_FILE_BYTES // 1_048_576} MB limit")
            remove_file(store, e.file_id)
            failures[e.file_id] = marker
            log({"action": "too_large", "path": e.path, "bytes": e.size})
            continue
        try:
            data = download_with_retry(client, e.path)
        except Exception as exc:
            print(f"    DOWNLOAD FAILED, old content kept, will retry: {type(exc).__name__}")
            log({"action": "download_failed", "path": e.path, "error": type(exc).__name__})
            continue
        res = extract(e.name, data)
        texts, metas, ids = chunk_file(e, res)
        remove_file(store, e.file_id)          # drop old chunks, including those under an old path
        if texts:
            store.add_texts(texts=texts, metadatas=metas, ids=ids)
            failures.pop(e.file_id, None)
        else:
            failures[e.file_id] = marker       # remembered, so it is not retried until it changes
        flag = "" if texts else "   <-- nothing indexed"
        print(f"    {res.status}, {len(texts)} chunks{flag}")
        log({"action": reason, "path": e.path, "status": res.status, "chunks": len(texts),
             "notes": res.notes, "error": res.error[:200], "skipped": res.skipped})

    if not dry_run:
        save_failures(failures)
    if known:
        print(f"  ({len(known)} file(s) produced nothing before and are unchanged; see {FAILURES_FILE})")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="show the plan, change nothing")
    parser.add_argument("--watch", type=int, metavar="SECONDS", help="repeat forever with this pause")
    args = parser.parse_args()
    while True:
        try:
            run_once(args.dry_run)
        except Exception as exc:
            print(f"sync cycle failed: {type(exc).__name__}: {exc}")
            log({"action": "cycle_failed", "error": type(exc).__name__})
        if not args.watch:
            break
        time.sleep(args.watch)