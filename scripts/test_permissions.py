import os

from kb.access import login
from kb.graph import build_graph
from kb.retrieval import retrieve

results = []


def check(name: str, ok: bool, detail: str = "") -> None:
    results.append(ok)
    print(f"{'PASS' if ok else 'FAIL'}  {name} {detail}")


def user(name: str):
    ctx = login(name, os.getenv(f"{name.upper()}_APP_PASSWORD", ""))
    assert ctx is not None, f"login failed for {name}"
    return ctx


def ask(ctx, question: str) -> dict:
    return build_graph(ctx).invoke({"question": question})


alice, bob = user("alice"), user("bob")
print("alice sees", alice.projects, "| bob sees", bob.projects, "\n")

# 1. Retrieval level, no LLM involved: what could ever reach the answer step
QUERIES = ["JWT authentication tokens", "database failover promote replica", "cold-chain pallets",
           "revenue by quarter", "card data retention", "scanned design notes idempotency"]
for ctx in (alice, bob):
    leaked, total = [], 0
    for q in QUERIES:
        for doc, _ in retrieve(q, ctx):
            total += 1
            if doc.metadata["project_id"] not in ctx.projects:
                leaked.append(doc.metadata["path"])
    check(f"{ctx.username}: retrieval returns only own projects", not leaked, f"({total} chunks checked) {leaked}")

# 2. End to end, answers must not contain facts that live only in a forbidden project
r = ask(bob, "What is the retry policy for failed push notifications?")
check("bob cannot learn Project A's notification policy",
      "notif-dlq" not in r["answer"] and "6 times" not in r["answer"], f"-> {r['answer'][:90]!r}")
r = ask(alice, "How fast must cold-chain pallets be moved after receipt?")
check("alice cannot learn Project B's cold-chain rule",
      "Bay 31" not in r["answer"] and "12 minutes" not in r["answer"], f"-> {r['answer'][:90]!r}")
r = ask(bob, "Find the file named Architecture.pdf in Project A")
check("bob finds no Project A files",
      not any("Project_A" in s["path"] for s in r.get("sources", [])), f"-> {r['answer'][:90]!r}")
r = ask(alice, "What was the Q1 revenue?")
check("alice gets Project A revenue without being asked which project",
      "120,000" in r["answer"] and "50,000" not in r["answer"], f"-> {r['answer'][:70]!r}")
r = ask(bob, "What was the Q1 revenue?")
check("bob gets Project B revenue only",
      "50,000" in r["answer"] and "120,000" not in r["answer"], f"-> {r['answer'][:70]!r}")

print(f"\n{sum(results)}/{len(results)} passed")