from kb.sync import indexed_state, plan_sync, split_known_failures
from tests.helpers import entry

VERSION = "x2|model|c1000-150"


def _indexed(file_id, path, etag, version=VERSION):
    return {"file_id": file_id, "path": path, "etag": etag, "index_version": version}


class FakeStore:
    def __init__(self, rows):
        self.rows = rows

    def get(self, include):
        return {"metadatas": self.rows}


def test_indexed_state_collapses_chunks_to_one_entry_per_file():
    store = FakeStore([_indexed("1", "Projects/A/a.txt", '"e1"'), _indexed("1", "Projects/A/a.txt", '"e1"')])
    assert list(indexed_state(store)) == ["1"]


def test_plan_classifies_every_case():
    files = [
        entry("Projects/Project_A/same.txt", "1", '"e1"'),          # unchanged
        entry("Projects/Project_A/edited.txt", "2", '"e2-new"'),     # modified
        entry("Projects/Project_B/moved.txt", "3", '"e3"'),          # moved between projects
        entry("Projects/Project_A/brand_new.txt", "4", '"e4"'),      # new
        entry("Projects/Project_A/old_index.txt", "5", '"e5"'),      # indexed with an older version
        entry("Projects/Project_A/renamed.txt", "7", '"e7"'),        # renamed
    ]
    state = indexed_state(FakeStore([
        _indexed("1", "Projects/Project_A/same.txt", '"e1"'),
        _indexed("2", "Projects/Project_A/edited.txt", '"e2"'),
        _indexed("3", "Projects/Project_A/moved.txt", '"e3"'),
        _indexed("5", "Projects/Project_A/old_index.txt", '"e5"', version="x1|model|c1000-150"),
        _indexed("6", "Projects/Project_A/gone.txt", '"e6"'),        # deleted in Nextcloud
        _indexed("7", "Projects/Project_A/before.txt", '"e7"'),
    ]))
    todo, deleted, unchanged = plan_sync(files, state, VERSION)
    assert {e.file_id: reason for e, reason in todo} == {
        "2": "modified", "3": "moved or renamed", "4": "new",
        "5": "index version changed", "7": "moved or renamed"}
    assert deleted == ["6"]
    assert unchanged == 1


def test_known_failures_are_skipped_only_while_nothing_changes():
    todo = [(entry("Projects/C/bad.pdf", "1", '"a"'), "new"),
            (entry("Projects/C/bad2.pdf", "2", '"b-changed"'), "modified"),
            (entry("Projects/C/bad3.pdf", "3", '"c"'), "index version changed"),
            (entry("Projects/C/moved.pdf", "4", '"d"'), "moved or renamed"),
            (entry("Projects/C/fresh.pdf", "5", '"e"'), "new")]
    failures = {
        "1": {"etag": '"a"', "path": "Projects/C/bad.pdf", "version": VERSION},
        "2": {"etag": '"b"', "path": "Projects/C/bad2.pdf", "version": VERSION},
        "3": {"etag": '"c"', "path": "Projects/C/bad3.pdf", "version": "x1|model|c1000-150"},
        "4": {"etag": '"d"', "path": "Projects/C/old_name.pdf", "version": VERSION},
    }
    retry, known = split_known_failures(todo, failures, VERSION)
    assert [e.file_id for e in known] == ["1"]
    assert [e.file_id for e, _ in retry] == ["2", "3", "4", "5"]