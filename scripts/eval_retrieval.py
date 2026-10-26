from kb.vectorstore import get_store

# (question, files that must appear in the top 5, text that must NOT appear)
TESTS = [
    ("Which project explains JWT authentication?",
     ["Project_A/Technical_Documents/Authentication_Guide.pdf",
      "Project_C/Technical_Documents/Authentication_Guide.pdf"], None),
    ("What is the retry policy for failed push notifications?", ["Technical_Design_Specification.docx"], None),
    ("How do I promote the database replica after a primary failure?", ["Operations_Runbook.pdf"], None),
    ("How fast must cold-chain pallets be moved after receipt?", ["Warehouse_Operations_Manual.pdf"], None),
    ("Why did Project B keep MySQL instead of PostgreSQL?", ["Design_Decisions.md"], None),
    ("How long are truncated card numbers retained?", ["Compliance_Handbook.docx"], None),
    ("Which security finding is still open?", ["Security_Review_Hybrid.pdf"], None),
    ("What was the Q1 revenue for Project A?", ["Project_A/Data/Project_Metrics.xlsx"], None),
    ("What is the maximum daily transfer limit?", ["Project_A/Requirements/Business_Requirements.docx"], None),   # exists only inside an image
]

store = get_store()
passed = 0
for question, expected, forbidden in TESTS:
    hits = store.similarity_search_with_score(question, k=5)
    paths = [d.metadata["path"] for d, _ in hits]
    if forbidden:
        ok = not any(forbidden in d.page_content for d, _ in hits)
        detail = f"'{forbidden}' absent from top 5 (it lives only in an image)"
    else:
        ranks = {x: next((i + 1 for i, p in enumerate(paths) if x in p), None) for x in expected}
        ok = all(r is not None for r in ranks.values())
        detail = ", ".join(f"{x.split('/')[-1]} rank {r}" for x, r in ranks.items())
    passed += ok
    print(f"{'PASS' if ok else 'FAIL'}  {question}\n      {detail}")
print(f"\n{passed}/{len(TESTS)} passed")