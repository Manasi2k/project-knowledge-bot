import os

from kb.access import login
from kb.retrieval import retrieve

ctx = login("bob", os.getenv("BOB_APP_PASSWORD", ""))
print("bob sees", ctx.projects)
before = retrieve("cold-chain pallets Bay 31", ctx)
print("before revoking:", len(before), "chunks returned")
if not before:
    raise SystemExit("PRECONDITION FAILED: bob has no access to start with. Re-share Project_B, then rerun.")

input("\nIn Nextcloud, as kb_service, remove Bob's share of Project_B. Press Enter when done...")

after = retrieve("cold-chain pallets Bay 31", ctx)   # same session, project list is now stale
print("after revoking:", len(after), "chunks returned (must be 0)")
print("PASS" if before and not after else "FAIL")