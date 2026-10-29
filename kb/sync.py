"""Decide what the index must change to match Nextcloud. Pure logic, no network."""
from kb.nextcloud_client import RemoteEntry


def indexed_state(store) -> dict[str, dict]:
    """What the index remembers per file, read back from the chunk metadata itself."""
    state: dict[str, dict] = {}
    for m in store.get(include=["metadatas"])["metadatas"]:
        state.setdefault(m["file_id"], {
            "etag": m.get("etag", ""), "path": m["path"], "version": m.get("index_version", "")})
    return state


def plan_sync(files: list[RemoteEntry], state: dict[str, dict], version: str):
    """Returns (files to (re)index with the reason, file IDs to remove, count unchanged)."""
    todo, unchanged = [], 0
    for e in files:
        s = state.get(e.file_id)
        if s is None:
            reason = "new"
        elif s["version"] != version:
            reason = "index version changed"
        elif s["path"] != e.path:
            reason = "moved or renamed"
        elif s["etag"] != (e.etag or ""):
            reason = "modified"
        else:
            unchanged += 1
            continue
        todo.append((e, reason))
    present = {e.file_id for e in files}
    deleted = sorted(fid for fid in state if fid not in present)
    return todo, deleted, unchanged

def split_known_failures(todo, failures: dict, version: str):
    """Separate files that already failed in exactly this state (skip them) from ones worth trying."""
    retry, known = [], []
    for e, reason in todo:
        f = failures.get(e.file_id)
        if f and f["etag"] == (e.etag or "") and f["path"] == e.path and f["version"] == version:
            known.append(e)
        else:
            retry.append((e, reason))
    return retry, known