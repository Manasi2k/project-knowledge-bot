"""LangGraph workflow: decide how to answer a question, then answer it with sources."""
import json
import os
from typing import Literal, Optional, TypedDict

from dotenv import load_dotenv
from langchain_groq import ChatGroq
from langgraph.graph import END, START, StateGraph
from pydantic import BaseModel, Field

from kb.access import UserContext, can_read, project_of
from kb.answer import answer
from kb.chat import small_talk
from kb.files import find_files
from kb.guardrails import redact
from kb.sheets import aggregate, describe

load_dotenv()
MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")


class State(TypedDict, total=False):
    question: str
    route: str            # semantic | file_search | spreadsheet | chitchat
    filename: str         # set by the router for file_search
    project: str          # set by the router, e.g. Project_B
    answer: str
    sources: list[dict]
    error: str


class Route(BaseModel):
    route: Literal["semantic", "file_search", "spreadsheet", "chitchat"]
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
- file_search: the person wants to find, open, download or see a file (a PDF, image, presentation, document, spreadsheet) by name, or asks where a file is. Put the file name (or part of it) in filename.
- spreadsheet: the question asks for a number to be looked up or calculated from a spreadsheet or workbook (revenue, totals, averages, counts).
- chitchat: a greeting, a thank-you, a statement about the person themself (for example "my name is Sam"), or a question about what the assistant can do. No documents are needed.
- semantic: everything else (explanations, summaries, which project used something, what a document says).
If a project is named, write it like Project_A. Question: {question}"""

PLANNER_PROMPT = """Plan one calculation on a spreadsheet to answer the question.
Use ONLY the workbooks, sheets and columns listed below. Copy the workbook path exactly.
Filter values must be written exactly as shown in the 'values' lists.
If nothing listed can answer the question, set feasible to false.

Catalog:
{catalog}

Question: {question}"""


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


def semantic_node(state: State, ctx: UserContext) -> State:
    try:
        text, sources = answer(state["question"], ctx)
        return {"answer": redact(text), "sources": sources}
    except Exception as exc:
        return {"answer": "Sorry, I could not search the documents right now.", "error": f"{type(exc).__name__}: {exc}"}


def chitchat_node(state: State, ctx: UserContext) -> State:
    try:
        return {"answer": small_talk(state["question"], ctx.display_name or ctx.username)}
    except Exception as exc:
        return {"answer": "Hi! I'm having trouble reaching my language model right now. Please try again in a moment.",
                "error": f"{type(exc).__name__}: {exc}"}


def _visible(ctx: UserContext, entries):
    """Keep only files in this user's projects that Nextcloud shows them right now."""
    return [e for e in entries if project_of(e.path) in ctx.projects and can_read(ctx.client, e.path, e.file_id)]


def file_node(state: State, ctx: UserContext) -> State:
    try:
        name = state.get("filename") or ""
        if not name:
            return {"answer": "Which file are you looking for? Please give a file name."}
        hits = []
        for candidate in dict.fromkeys([name, name.replace(" ", "_")]):   # "architecture diagram" also tries architecture_diagram
            hits = _visible(ctx, find_files(ctx.service, candidate, state.get("project") or None))
            if hits:
                break
        if not hits:
            where = f" in {state['project']}" if state.get("project") else ""
            return {"answer": f"I couldn't find a file matching \"{name}\"{where} in the projects you can access. "
                              "Try part of the file name, or tell me which project to look in."}
        intro = (f'I found **{len(hits)} files** matching "{name}":' if len(hits) > 1
                 else "I found the file you asked for:")
        lines = [intro, ""] + [f"- **{e.name}** in `{e.path.removeprefix('Projects/')}`" for e in hits]
        lines += ["", "You can download or preview them below, or open them in Nextcloud."]
        sources = [{"n": i, "path": e.path, "location": "file", "method": "file search",
                    "url": f"{ctx.base_url}/f/{e.file_id}", "size": e.size} for i, e in enumerate(hits, 1)]
        return {"answer": "\n".join(lines), "sources": sources}
    except Exception as exc:
        return {"answer": "Sorry, I could not search the file system right now.", "error": f"{type(exc).__name__}: {exc}"}


def spreadsheet_node(state: State, ctx: UserContext) -> State:
    try:
        project = state.get("project") or None
        books = _visible(ctx, find_files(ctx.service, ".xlsx", project))
        if not books:
            return {"answer": "No Excel workbooks were found" + (f" in {project}." if project else ".")}
        projects = sorted({project_of(e.path) for e in books})
        if not project and len(projects) > 1:
            return {"answer": f"I found workbooks in several projects ({', '.join(projects)}). Which project should I use?"}
        data, catalog = {}, []
        for e in books:
            data[e.path] = ctx.client.download(e.path.removeprefix("Projects/"))   # read as the user
            catalog += [f"{e.path} | {line}" for line in describe(data[e.path])]
        plan = _structured(SheetPlan, PLANNER_PROMPT.format(catalog="\n".join(catalog), question=state["question"]))
        if not plan.feasible or plan.workbook not in data:
            return {"answer": "I could not find a spreadsheet column that answers that question."}
        where = {f.column: f.value for f in plan.filters}
        r = aggregate(data[plan.workbook], plan.sheet, plan.column, plan.op, where)
        if not r.rows:
            return {"answer": f"No rows matched {where} on sheet '{plan.sheet}' of {plan.workbook}."}
        value = f"{r.value:,.0f}" if float(r.value).is_integer() else f"{r.value:,.2f}"
        label = {"sum": "total", "mean": "average", "min": "lowest value", "max": "highest value",
                 "count": "count"}[plan.op]
        cond = (" for " + ", ".join(f"**{v}**" for v in where.values())) if where else ""
        rows = f"row {r.rows[0]}" if len(r.rows) == 1 else f"rows {r.rows[0]}-{r.rows[-1]}"
        text = (f"The {label} of **{r.column}**{cond} is **{value}**.\n\n"
                f"I calculated it from the *{r.sheet}* sheet of `{plan.workbook.removeprefix('Projects/')}` "
                f"({rows}, {len(r.rows)} row{'s' if len(r.rows) != 1 else ''} used). "
                "Python did the arithmetic, not the AI, so the number is exact.")
        entry = next(e for e in books if e.path == plan.workbook)
        return {"answer": text, "sources": [{"n": 1, "path": plan.workbook, "location": f"sheet {r.sheet}",
                                             "method": "structured", "url": f"{ctx.base_url}/f/{entry.file_id}"}]}
    except Exception as exc:
        return {"answer": "Sorry, I could not calculate that from the spreadsheet.", "error": f"{type(exc).__name__}: {exc}"}


def build_graph(ctx: UserContext):
    g = StateGraph(State)
    g.add_node("route", route_node)
    g.add_node("chitchat", lambda s: chitchat_node(s, ctx))
    g.add_node("semantic", lambda s: semantic_node(s, ctx))
    g.add_node("file_search", lambda s: file_node(s, ctx))
    g.add_node("spreadsheet", lambda s: spreadsheet_node(s, ctx))
    g.add_edge(START, "route")
    g.add_conditional_edges("route", lambda s: s["route"], ["semantic", "file_search", "spreadsheet", "chitchat"])
    for name in ("semantic", "file_search", "spreadsheet", "chitchat"):
        g.add_edge(name, END)
    return g.compile()