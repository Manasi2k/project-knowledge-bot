"""Permission-aware semantic retrieval: filter the index, then re-check every hit with Nextcloud."""
from kb.access import UserContext, can_read


def retrieve(question: str, ctx: UserContext, k: int = 6, store=None):
    """Top-k (document, distance) pairs this user may read. Nothing else leaves this function."""
    if not ctx.projects:
        return []
    if store is None:
        from kb.vectorstore import get_store
        store = get_store()
    hits = store.similarity_search_with_score(
        question, k=k * 2, filter={"project_id": {"$in": ctx.projects}})
    allowed, checked = [], {}
    for doc, distance in hits:
        m = doc.metadata
        key = (m["path"], m["file_id"])
        if key not in checked:
            checked[key] = can_read(ctx.client, m["path"], m["file_id"])
        if checked[key]:
            allowed.append((doc, distance))
            if len(allowed) == k:
                break
    return allowed