import os
import sys
import time

from kb.access import login
from kb.answer import answer
from kb.graph import route_node
from kb.retrieval import retrieve

user, question = sys.argv[1], " ".join(sys.argv[2:])


def timed(label, fn):
    start = time.perf_counter()
    result = fn()
    print(f"{label:34s} {time.perf_counter() - start:6.2f} s")
    return result


ctx = timed("sign-in", lambda: login(user, os.getenv(f"{user.upper()}_APP_PASSWORD", "")))
timed("router (Groq call)", lambda: route_node({"question": question}))
timed("retrieval, first call (loads model)", lambda: retrieve(question, ctx))
timed("retrieval, warm", lambda: retrieve(question, ctx))
timed("full semantic answer (retrieve+Groq)", lambda: answer(question, ctx))
