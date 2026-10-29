"""Conversation helpers: understanding follow-up questions, and small talk."""
import os
import re

from dotenv import load_dotenv
from langchain_groq import ChatGroq

load_dotenv()
MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
HISTORY_MESSAGES = 6   # how many recent messages are used as context

SMALL_TALK_SYSTEM = (
    "You are a friendly assistant for a company's project knowledge base. "
    "Reply briefly and warmly to greetings, thanks, statements about the person, and questions about what you can do. "
    "You can answer questions about project documents, find files and let people download them, "
    "show image files, and calculate totals from spreadsheets. "
    "You cannot see any document in this reply, so if the person asks about project facts, "
    "ask them to put the question directly so you can search. "
    "Never state facts about projects, people, numbers or files. "
    "You do not remember earlier conversations. "
    "The person is signed in as {who}. Address them by that name. If they say their name is something else, "
    "be polite and say you only know the name on their account."
)


def _llm() -> ChatGroq:
    return ChatGroq(model=MODEL, temperature=0)


def condense(history: list[dict], question: str) -> str:
    """Rewrite a follow-up such as 'what about Project B?' into a question that stands on its own."""
    recent = [m for m in history if not m.get("error")][-HISTORY_MESSAGES:]
    if not recent:
        return question
    transcript = "\n".join(
        f"{'User' if m['role'] == 'user' else 'Assistant'}: {m['content'][:600]}" for m in recent)
    prompt = (
        "Below is a conversation and a new user message. Rewrite the new message as one complete, "
        "standalone message that keeps every project, file and topic the user is referring to. "
        "If it is already standalone, a greeting, or a thank-you, return it unchanged. "
        "Reply with ONLY the rewritten message.\n\n"
        f"Conversation:\n{transcript}\n\nNew message: {question}")
    try:
        rewritten = _llm().invoke(prompt).content.strip()
        return rewritten if 0 < len(rewritten) <= 500 else question
    except Exception:
        return question          # fall back to the original question


def small_talk(question: str, who: str = "an employee") -> str:
    return _llm().invoke([("system", SMALL_TALK_SYSTEM.format(who=who)), ("human", question)]).content




# ---------- questions about the signed-in user, answered from the login, not from documents ----------
_ACCOUNT_PATTERNS = [
    r"who am i", r"who am i (logged|signed) in as", r"am i (logged|signed) in",
    r"(what is|whats) my (name|username|user name|account)", r"which account am i (using|signed in with)",
    r"(what|which) projects (do i have access to|can i access|can i see|can i search|do i have)",
    r"what (can i access|do i have access to|can i see)", r"my (access|permissions|projects)",
]


def identity_answer(question: str, ctx) -> str | None:
    """A reply built from the verified sign-in if the question is about the user's own account, else None."""
    normalised = " ".join(re.sub(r"[^a-z0-9 ]", "", question.lower()).split())
    if not any(re.fullmatch(p, normalised) for p in _ACCOUNT_PATTERNS):
        return None
    access = (f"You can search these projects: {', '.join(f'**{p}**' for p in ctx.projects)}."
              if ctx.projects else "You don't have access to any projects yet.")
    name = getattr(ctx, "display_name", "") or ctx.username
    who = f"**{name}** (account `{ctx.username}`)" if name != ctx.username else f"**{ctx.username}**"
    return f"You're signed in as {who}. {access}"