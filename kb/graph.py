"""LangGraph workflow: decide how to answer a question, then answer it with sources."""
import os
import json
from typing import Literal, Optional, TypedDict

from dotenv import load_dotenv
from langchain_groq import ChatGroq
from langgraph.graph import END, START, StateGraph
from pydantic import BaseModel, Field

from kb.answer import answer
from kb.config import load_nextcloud_settings
from kb.files import find_files
from kb.nextcloud_client import NextcloudClient
from kb.sheets import aggregate, describe

load_dotenv()
MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")


class State(TypedDict, total=False):
    question: str
    route: str            # semantic | file_search | spreadsheet
    filename: str         # set by the router for file_search
    project: str          # set by the router, e.g. Project_B
    answer: str
    sources: list[dict]
    error: str


class Route(BaseModel):
    route: Literal["semantic", "file_search", "spreadsheet"]
    filename: Optional[str] = Field(None, description="File name or part of it, for file_search only")
    project: Optional[str] = Field(None, description="Project in the form Project_A, only if the question names one")


class Filter(BaseModel):
    column: str
    value: str


class SheetPlan(BaseModel):
    feasible: bool = Field(description="False if no sheet and column in the catalog can answer the question")
    workbook: str = ""
    sheet: str = ""
    column: str = ""
    op: Literal["sum", "mean", "min", "max", "count"] = "sum"
    filters: list[Filter] = []


ROUTER_PROMPT = """Choose how to answer a question about company project documents.
- file_search: the person wants to locate or open a file by name, or asks where a file is. Put the file name (or part of it) in filename.
- spreadsheet: the question asks for a number to be looked up or calculated from a spreadsheet or workbook (revenue, totals, averages, counts).
- semantic: everything else (explanations, summaries, which project used something, what a document says).
If a project is named, write it like Project_A. Question: {question}"""

PLANNER_PROMPT = """Plan one calculation on a spreadsheet to answer the question.
Use ONLY the workbooks, sheets and columns listed below. Copy the workbook path exactly.
Filter values must be written exactly as shown in the 'values' lists.
If nothing listed can answer the question, set feasible to false.

Catalog:
{catalog}

Question: {question}"""


def _client() -> tuple[NextcloudClient, str]:
    settings = load_nextcloud_settings()
    return NextcloudClient(settings), settings.base_url


def _llm() -> ChatGroq:
    return ChatGroq(model=MODEL, temperature=0)


def _structured(schema, prompt: str, attempts: int = 2):
    """Ask Groq for JSON matching `schema`. JSON mode avoids the tool_use_failed error."""
    instruction = (prompt + "\n\nReply with ONLY a JSON object matching this JSON schema, no other text:\n"
                   + json.dumps(schema.model_json_schema()))
    last_error: Exception | None = None
    for _ in range(attempts):
        try:
            return _llm().with_structured_output(schema, method="json_mode").invoke(instruction)
        except Exception as exc:
            last_error = exc
    raise last_error


def route_node(state: State) -> State:
    try:
        decision = _structured(Route, ROUTER_PROMPT.format(question=state["question"]))
        project = (decision.project or "").strip().replace(" ", "_")   # "Project B" -> "Project_B"
        return {"route": decision.route, "filename": decision.filename or "", "project": project}
    except Exception:
        return {"route": "semantic", "filename": "", "project": ""}   # safe default


def semantic_node(state: State) -> State:
    try:
        _, base = _client()
        text, sources = answer(state["question"], base)
        return {"answer": text, "sources": sources}
    except Exception as exc:
        return {"answer": "Sorry, I could not search the documents right now.", "error": f"{type(exc).__name__}: {exc}"}


def file_node(state: State) -> State:
    try:
        client, base = _client()
        name = state.get("filename") or ""
        if not name:
            return {"answer": "Which file are you looking for? Please give a file name."}
        hits = find_files(client, name, state.get("project") or None)
        if not hits:
            where = f" in {state['project']}" if state.get("project") else ""
            return {"answer": f"No file matching '{name}'{where} was found."}
        lines = [f"Found {len(hits)} file(s) matching '{name}':"] + [f"- {e.path}" for e in hits]
        sources = [{"n": i, "path": e.path, "location": "file", "method": "file search",
                    "url": f"{base}/f/{e.file_id}"} for i, e in enumerate(hits, 1)]
        return {"answer": "\n".join(lines), "sources": sources}
    except Exception as exc:
        return {"answer": "Sorry, I could not search the file system right now.", "error": f"{type(exc).__name__}: {exc}"}


def spreadsheet_node(state: State) -> State:
    try:
        client, base = _client()
        project = state.get("project") or None
        books = find_files(client, ".xlsx", project)
        if not books:
            return {"answer": "No Excel workbooks were found" + (f" in {project}." if project else ".")}
        projects = sorted({e.path.split("/")[1] for e in books})
        if not project and len(projects) > 1:
            return {"answer": f"Several projects have workbooks ({', '.join(projects)}). Which project do you mean?"}
        data, catalog = {}, []
        for e in books:
            data[e.path] = client.download(e.path)
            catalog += [f"{e.path} | {line}" for line in describe(data[e.path])]
        plan = _structured(SheetPlan, PLANNER_PROMPT.format(catalog="\n".join(catalog), question=state["question"]))
        if not plan.feasible or plan.workbook not in data:
            return {"answer": "I could not find a spreadsheet column that answers that question."}
        where = {f.column: f.value for f in plan.filters}
        r = aggregate(data[plan.workbook], plan.sheet, plan.column, plan.op, where)
        if not r.rows:
            return {"answer": f"No rows matched {where} on sheet '{plan.sheet}' of {plan.workbook}."}
        value = f"{r.value:,.0f}" if float(r.value).is_integer() else f"{r.value:,.2f}"
        cond = f" where {', '.join(f'{k}={v}' for k, v in where.items())}" if where else ""
        text = (f"{plan.op} of {r.column}{cond} = {value}\n"
                f"(workbook {plan.workbook}, sheet '{r.sheet}', spreadsheet rows {r.rows[0]}-{r.rows[-1]}, "
                f"{len(r.rows)} row(s) used; calculated by Python, not by the language model)")
        entry = next(e for e in books if e.path == plan.workbook)
        return {"answer": text, "sources": [{"n": 1, "path": plan.workbook, "location": f"sheet {r.sheet}",
                                             "method": "structured", "url": f"{base}/f/{entry.file_id}"}]}
    except Exception as exc:
        return {"answer": "Sorry, I could not calculate that from the spreadsheet.", "error": f"{type(exc).__name__}: {exc}"}


def build_graph():
    g = StateGraph(State)
    g.add_node("route", route_node)
    g.add_node("semantic", semantic_node)
    g.add_node("file_search", file_node)
    g.add_node("spreadsheet", spreadsheet_node)
    g.add_edge(START, "route")
    g.add_conditional_edges("route", lambda s: s["route"], ["semantic", "file_search", "spreadsheet"])
    for name in ("semantic", "file_search", "spreadsheet"):
        g.add_edge(name, END)
    return g.compile()