from types import SimpleNamespace

from kb.chat import identity_answer

ALICE = SimpleNamespace(username="alice", projects=["Project_A", "Project_C"], display_name="Manasi")


def test_account_questions_are_answered_from_the_login():
    for q in ["who am i", "Who am I?", "What's my username?", "which projects can I access?", "what can I access"]:
        answer = identity_answer(q, ALICE)
        assert "Manasi" in answer and "`alice`" in answer and "Project_A" in answer


def test_questions_that_only_look_similar_go_to_the_normal_route():
    for q in ["Who am I supposed to contact for Project A?", "What is my manager's name in Project B?",
              "my name is alice", "Which project uses JWT?"]:
        assert identity_answer(q, ALICE) is None


def test_no_display_name_falls_back_to_username_and_no_projects_is_explained():
    plain = SimpleNamespace(username="carol", projects=[], display_name="")
    answer = identity_answer("who am i", plain)
    assert "**carol**" in answer and "don't have access to any projects" in answer