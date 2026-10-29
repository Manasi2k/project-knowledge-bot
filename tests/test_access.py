from kb.access import allowed_projects, can_read, project_of
from tests.helpers import FakeClient, entry

SERVICE = FakeClient({"Projects": [entry("Projects/Project_A", "183", is_dir=True),
                                   entry("Projects/Project_B", "181", is_dir=True),
                                   entry("Projects/Project_C", "182", is_dir=True)]})


def test_project_of():
    assert project_of("Projects/Project_A/Data/x.xlsx") == "Project_A"
    assert project_of("Other/Project_A/x.txt") == ""


def test_allowed_projects_compares_ids_not_just_names():
    alice = FakeClient({"": [entry("Project_A", "183", is_dir=True),
                             entry("Project_B", "999", is_dir=True),   # her own folder with a copied name
                             entry("Notes", "5", is_dir=True)]})
    assert allowed_projects(alice, SERVICE) == ["Project_A"]


def test_can_read_checks_existence_id_and_location():
    alice = FakeClient({"Project_A/Technical_Documents": [entry("Project_A/Technical_Documents/Architecture.pdf", "216")]})
    path = "Projects/Project_A/Technical_Documents/Architecture.pdf"
    assert can_read(alice, path, "216")
    assert not can_read(alice, path, "217")                                        # same name, different file
    assert not can_read(alice, "Projects/Project_A/Technical_Documents/Nope.pdf")  # does not exist
    assert not can_read(alice, "Projects/Project_B/Technical_Documents/x.pdf")     # folder not visible
    assert not can_read(alice, "Elsewhere/x.pdf")                                  # outside Projects