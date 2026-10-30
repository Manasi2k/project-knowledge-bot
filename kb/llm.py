"""One place that decides which language model is used. Everything else calls these functions."""
import json
import os

from dotenv import load_dotenv

load_dotenv()


def provider() -> str:
    return os.getenv("LLM_PROVIDER", "groq").strip().lower()


def get_llm():
    """Groq by default (free, works anywhere). LLM_PROVIDER=vertex uses Google's Vertex AI instead."""
    if provider() == "vertex":
        from langchain_google_genai import ChatGoogleGenerativeAI
        return ChatGoogleGenerativeAI(
            model=os.environ["VERTEX_MODEL"],                       # pick one from your Vertex AI model list
            project=os.environ["GOOGLE_CLOUD_PROJECT"],
            location=os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1"),
            vertexai=True,
            temperature=0,
        )
    from langchain_groq import ChatGroq
    return ChatGroq(model=os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile"), temperature=0)


def text_of(content) -> str:
    """Models return either a string or a list of content blocks. Always give back plain text."""
    if isinstance(content, str):
        return content
    parts = []
    for block in content or []:
        if isinstance(block, str):
            parts.append(block)
        elif isinstance(block, dict) and block.get("type") == "text":
            parts.append(block.get("text", ""))
    return "".join(parts)


def structured(schema, prompt: str, attempts: int = 2):
    """Ask the model for an answer shaped like `schema` (a pydantic class)."""
    llm = get_llm()
    if provider() == "groq":
        # Groq's tool-calling mode fails now and then (tool_use_failed), so use JSON mode with the schema in the prompt
        prompt += ("\n\nReply with ONLY a JSON object matching this JSON schema, no other text:\n"
                   + json.dumps(schema.model_json_schema()))
        runnable = llm.with_structured_output(schema, method="json_mode")
    else:
        runnable = llm.with_structured_output(schema)
    last_error: Exception | None = None
    for _ in range(attempts):
        try:
            return runnable.invoke(prompt)
        except Exception as exc:
            last_error = exc
    raise last_error