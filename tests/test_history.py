import time

import pytest

import kb.history as history


@pytest.fixture(autouse=True)
def temp_db(tmp_path, monkeypatch):
    monkeypatch.setattr(history, "DB_PATH", str(tmp_path / "chats.db"))


def test_title_comes_from_first_question_and_messages_round_trip():
    chat = history.new_chat("alice")
    history.add_message("alice", chat, "user", "Which project used JWT authentication? " + "x" * 80)
    history.add_message("alice", chat, "assistant", "Project A and C.", route="semantic",
                        sources=[{"n": 1, "path": "p"}], files=[{"name": "a.pdf", "url": "u"}])
    assert history.list_chats("alice")[0]["title"] == ("Which project used JWT authentication? " + "x" * 80)[:45]
    messages = history.load_messages("alice", chat)
    assert [m["role"] for m in messages] == ["user", "assistant"]
    assert messages[1]["sources"] == [{"n": 1, "path": "p"}]
    assert messages[1]["files"] == [{"name": "a.pdf", "url": "u"}]


def test_another_user_cannot_read_write_or_delete_a_chat():
    chat = history.new_chat("alice")
    history.add_message("alice", chat, "user", "secret question")
    assert history.load_messages("bob", chat) == []
    with pytest.raises(PermissionError):
        history.add_message("bob", chat, "user", "sneaky")
    history.delete_chat("bob", chat)
    assert len(history.load_messages("alice", chat)) == 1


def test_sql_injection_style_username_matches_nothing():
    history.add_message("alice", history.new_chat("alice"), "user", "hello")
    assert history.list_chats("x' OR '1'='1") == []


def test_recently_used_chat_moves_to_the_top():
    first = history.new_chat("alice")
    history.add_message("alice", first, "user", "first chat")
    time.sleep(0.01)
    second = history.new_chat("alice")
    history.add_message("alice", second, "user", "second chat")
    assert [c["title"] for c in history.list_chats("alice")] == ["second chat", "first chat"]
    time.sleep(0.01)
    history.add_message("alice", first, "user", "back to the first")
    assert history.list_chats("alice")[0]["title"] == "first chat"


def test_old_chats_are_purged_and_new_ones_kept(tmp_path):
    import sqlite3
    old, new = history.new_chat("alice"), history.new_chat("alice")
    history.add_message("alice", old, "user", "old")
    history.add_message("alice", new, "user", "new")
    con = sqlite3.connect(history.DB_PATH)
    con.execute("UPDATE chats SET updated = ? WHERE id = ?", (time.time() - 100 * 86400, old))
    con.commit()
    con.close()
    assert history.purge_old() == 1
    assert history.load_messages("alice", old) == []
    assert len(history.load_messages("alice", new)) == 1