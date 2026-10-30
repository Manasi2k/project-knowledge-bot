import os
import time

from kb.graph import PLANNER_PROMPT, ROUTER_PROMPT, Route, SheetPlan
from kb.llm import get_llm, provider, structured, text_of

print("provider:", provider(), "| model:", os.getenv("VERTEX_MODEL"), "| location:", os.getenv("GOOGLE_CLOUD_LOCATION"))

start = time.perf_counter()
reply = get_llm().invoke("Reply with exactly: Vertex is working")
print(f"1. plain reply ({time.perf_counter() - start:.1f}s):", text_of(reply.content))

route = structured(Route, ROUTER_PROMPT.format(question="Find the file named Architecture.pdf in Project B"))
print("2. router:", route)

catalog = ("Projects/Project_A/Data/Project_Metrics.xlsx | sheet 'Revenue': "
           "Quarter (values: Q1, Q2, Q3, Q4); Region (values: North, South, West); Revenue_USD")
plan = structured(SheetPlan, PLANNER_PROMPT.format(catalog=catalog, question="What was the Q1 revenue for Project A?"))
print("3. planner:", plan)