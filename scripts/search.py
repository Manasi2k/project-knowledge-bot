import sys

from kb.vectorstore import get_store

question = " ".join(sys.argv[1:])
for doc, distance in get_store().similarity_search_with_score(question, k=5):
    m = doc.metadata
    print(f"{distance:.3f}  {m['path']}  [{m['location']}, {m['method']}]")
    print("       ", doc.page_content.split("\n", 1)[-1][:150].replace("\n", " "))
    