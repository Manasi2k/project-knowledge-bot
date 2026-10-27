import os
import sys

from kb.access import login
from kb.graph import build_graph

user, question = sys.argv[1], " ".join(sys.argv[2:])
ctx = login(user, os.getenv(f"{user.upper()}_APP_PASSWORD", ""))
if ctx is None:
    sys.exit(f"Login failed for {user}")

result = build_graph(ctx).invoke({"question": question})
print(f"[user: {user} | projects: {ctx.projects} | route: {result.get('route')}]\n")
print(result["answer"])
if result.get("sources"):
    print("\nSources:")
    for s in result["sources"]:
        print(f"[{s['n']}] {s['path']} ({s['location']}, {s['method']})\n     {s['url']}")
if result.get("error"):
    print("\nINTERNAL ERROR:", result["error"])