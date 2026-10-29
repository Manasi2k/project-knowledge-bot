import logging
import mimetypes

import streamlit as st

from kb.access import login
from kb.chat import condense, identity_answer
from kb.graph import build_graph
from kb.guardrails import check_question, rate_limited, redact
from kb.history import add_message, delete_chat, list_chats, load_messages, new_chat, purge_old
from kb.vectorstore import get_store

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("kb.app")

MAX_FILES_SHOWN = 3
MAX_DOWNLOAD_BYTES = 10 * 1024 * 1024
IMAGE_EXTENSIONS = (".png", ".jpg", ".jpeg")

st.set_page_config(page_title="Project Knowledge Bot", page_icon="📁")


@st.cache_resource(show_spinner="Loading the search model (first start only)...")
def warm_up() -> bool:
    get_store().similarity_search("warm up", k=1)
    return True


warm_up()


# ---------- actions used by buttons ----------
def sign_out() -> None:
    for key in ("ctx", "graph", "messages", "asked", "chat_id"):
        st.session_state.pop(key, None)


def start_new_chat() -> None:
    st.session_state.chat_id = None
    st.session_state.messages = []


def open_chat(chat_id: str) -> None:
    st.session_state.chat_id = chat_id
    st.session_state.messages = load_messages(st.session_state.ctx.username, chat_id)


def remove_chat() -> None:
    delete_chat(st.session_state.ctx.username, st.session_state.chat_id)
    start_new_chat()


# ---------- display helpers ----------
def render_sources(sources: list[dict]) -> None:
    if not sources:
        return
    with st.expander(f"Sources ({len(sources)})"):
        for s in sources:
            note = " — read by OCR, may contain errors" if s.get("method") == "ocr" else ""
            st.markdown(f"**[{s['n']}]** [{s['path']}]({s['url']}) · {s['location']}{note}")


def prepare_files(ctx, sources: list[dict]) -> list[dict]:
    """Fetch the files a file search found, AS THE SIGNED-IN USER, so Nextcloud enforces access."""
    files = []
    for s in sources[:MAX_FILES_SHOWN]:
        name = s["path"].rsplit("/", 1)[-1]
        if s.get("size") and s["size"] > MAX_DOWNLOAD_BYTES:
            files.append({"name": name, "too_large": True, "url": s["url"]})
            continue
        try:
            data = ctx.client.download(s["path"].removeprefix("Projects/"))
        except Exception:
            log.exception("file download failed")
            continue
        files.append({"name": name, "data": data, "url": s["url"],
                      "mime": mimetypes.guess_type(name)[0] or "application/octet-stream"})
    return files


def render_files(files: list[dict], key_prefix: str) -> None:
    for i, f in enumerate(files):
        if f.get("too_large"):
            st.markdown(f"**{f['name']}** is over 10 MB. [Open it in Nextcloud]({f['url']})")
        elif "data" not in f:       # a chat restored from history: link only, no stored file contents
            st.markdown(f"📎 [{f['name']}]({f['url']}) — open in Nextcloud")
        else:
            if f["name"].lower().endswith(IMAGE_EXTENSIONS):
                st.image(f["data"], caption=f["name"])
            st.download_button(f"Download {f['name']}", f["data"], file_name=f["name"],
                               mime=f["mime"], key=f"{key_prefix}-{i}")


def run_graph(graph, question: str, box) -> dict:
    """Run the workflow. Tokens of the answer step appear live; returns the final state."""
    final, streamed = {}, ""
    for mode, data in graph.stream({"question": question}, stream_mode=["messages", "values"]):
        if mode == "values":
            final = data
        elif mode == "messages":
            chunk, meta = data
            if meta.get("langgraph_node") in ("semantic", "chitchat") and chunk.content:
                streamed += chunk.content
                box.markdown(redact(streamed) + "▌")
    return final or {"answer": "Sorry, something went wrong.", "error": "workflow returned no result"}


# ---------- sign-in ----------
if "ctx" not in st.session_state:
    st.title("Project Knowledge Bot")
    with st.form("login"):
        username = st.text_input("Nextcloud username")
        password = st.text_input("Nextcloud app password", type="password")
        submitted = st.form_submit_button("Sign in")
    if submitted:
        try:
            ctx = login(username.strip(), password)
        except Exception:
            log.exception("sign-in failed with a system error")
            st.error("Sign-in is unavailable right now. Please try again later.")
            st.stop()
        if ctx is None:
            st.error("Sign-in failed. Check your username and app password.")
        else:
            purge_old()                         # delete chats older than the retention period
            st.session_state.ctx = ctx          # the password itself is not kept
            st.session_state.graph = build_graph(ctx)
            st.session_state.messages = []
            st.session_state.chat_id = None
            st.session_state.asked = []
            st.rerun()
    st.stop()

# ---------- sidebar: chats ----------
ctx = st.session_state.ctx
with st.sidebar:
    st.markdown(f"Signed in as **{ctx.username}**")
    st.caption("Projects you can search: " + (", ".join(ctx.projects) or "none"))
    st.button("➕ New chat", on_click=start_new_chat, use_container_width=True)
    st.markdown("**Your chats**")
    chats = list_chats(ctx.username)
    if not chats:
        st.caption("No saved chats yet.")
    for c in chats:
        label = ("● " if c["id"] == st.session_state.chat_id else "") + c["title"]
        st.button(label, key=f"chat-{c['id']}", on_click=open_chat, args=(c["id"],), use_container_width=True)
    if st.session_state.chat_id:
        st.button("🗑 Delete this chat", on_click=remove_chat)
    st.divider()
    st.caption("Chats are saved for 90 days.")
    st.button("Sign out", on_click=sign_out)

# ---------- chat ----------
st.title("Project Knowledge Bot")
if not ctx.projects:
    st.warning("You do not have access to any projects yet. Please ask your administrator.")

for idx, m in enumerate(st.session_state.messages):
    with st.chat_message(m["role"]):
        if m.get("error"):
            st.error(m["content"])
        else:
            st.markdown(m["content"])
            render_files(m.get("files", []), f"hist-{idx}")
            render_sources(m.get("sources", []))
            if m.get("route"):
                st.caption(f"answered by: {m['route']}")

question = st.chat_input("Ask about your projects...")
if question:
    problem = check_question(question)
    if problem:
        st.warning(problem)
    elif rate_limited(st.session_state.asked):
        st.warning("You have asked a lot of questions in a short time. Please wait a few minutes.")
    else:
        st.session_state.messages.append({"role": "user", "content": question})
        with st.chat_message("user"):
            st.markdown(question)
        with st.chat_message("assistant"):
            box = st.empty()
            box.markdown("_Thinking..._")
            quick = identity_answer(question, ctx)    # "who am I?" is answered from the sign-in, not from documents
            if quick:
                result = {"answer": quick, "route": "account", "sources": []}
            else:
                standalone = condense(st.session_state.messages[:-1], question)   # understands follow-ups
                if standalone != question:
                    box.markdown(f"_Searching for: {standalone}_")
                result = run_graph(st.session_state.graph, standalone, box)
            is_error = bool(result.get("error"))
            files = []
            if is_error:
                log.warning("graph error: %s", result["error"])   # details go to the log, not the page
                box.error(result["answer"])
            else:
                box.markdown(result["answer"])                    # final text, citations tidied
                if result.get("route") == "file_search":
                    files = prepare_files(ctx, result.get("sources", []))
                    render_files(files, f"new-{len(st.session_state.messages)}")
                render_sources(result.get("sources", []))
                st.caption(f"answered by: {result.get('route')}")
        st.session_state.messages.append({
            "role": "assistant", "content": result["answer"], "sources": result.get("sources", []),
            "files": files, "error": is_error, "route": result.get("route")})

        if not is_error:                                          # save the exchange (failed ones are not saved)
            created = st.session_state.chat_id is None
            if created:
                st.session_state.chat_id = new_chat(ctx.username)
            add_message(ctx.username, st.session_state.chat_id, "user", question)
            add_message(ctx.username, st.session_state.chat_id, "assistant", result["answer"],
                        sources=result.get("sources", []),
                        files=[{"name": f["name"], "url": f["url"]} for f in files],
                        route=result.get("route"))
            if created:
                st.rerun()                                        # so the new chat appears in the sidebar