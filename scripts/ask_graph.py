import sys

from kb.graph import build_graph

question = " ".join(sys.argv[1:])
result = build_graph().invoke({"question": question})
print(f"[route: {result.get('route')}]\n")
print(result["answer"])
if result.get("sources"):
    print("\nSources:")
    for s in result["sources"]:
        print(f"[{s['n']}] {s['path']} ({s['location']}, {s['method']})\n     {s['url']}")
if result.get("error"):
    print("\nINTERNAL ERROR:", result["error"])