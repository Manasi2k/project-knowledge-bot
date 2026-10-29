from types import SimpleNamespace

from kb.access import UserContext
from kb.retrieval import retrieve
from tests.helpers import FakeClient, entry


def _doc(path, file_id, project):
    return SimpleNamespace(metadata={"path": path, "file_id": file_id, "project_id": project}, page_content="text")


class FakeStore:
    def __init__(self, hits):
        self.hits, self.call = hits, None

    def similarity_search_with_score(self, question, k, filter):
        self.call = {"k": k, "filter": filter}
        return self.hits


def _ctx(user_client, projects):
    return UserContext("alice", user_client, FakeClient({}), projects, "http://x")


def test_filters_the_index_by_project_and_drops_files_nextcloud_no_longer_shows():
    alice = FakeClient({"Project_A/Technical_Documents": [entry("Project_A/Technical_Documents/Architecture.pdf", "216")]})
    store = FakeStore([
        (_doc("Projects/Project_A/Technical_Documents/Architecture.pdf", "216", "Project_A"), 0.5),   # fine
        (_doc("Projects/Project_A/Technical_Documents/Architecture.pdf", "OLD-ID", "Project_A"), 0.6),  # replaced file
        (_doc("Projects/Project_A/Technical_Documents/Deleted.pdf", "1", "Project_A"), 0.7),          # deleted
    ])
    hits = retrieve("question", _ctx(alice, ["Project_A"]), k=6, store=store)
    assert store.call["filter"] == {"project_id": {"$in": ["Project_A"]}}
    assert [d.metadata["file_id"] for d, _ in hits] == ["216"]


def test_user_without_projects_gets_nothing_and_the_index_is_never_queried():
    store = FakeStore([])
    assert retrieve("question", _ctx(FakeClient({}), []), store=store) == []
    assert store.call is None