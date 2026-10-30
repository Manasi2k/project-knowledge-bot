from dotenv import load_dotenv

load_dotenv()

import os

from google import genai

project = os.environ["GOOGLE_CLOUD_PROJECT"]
models = ["gemini-3.8-flash", "gemini-3.5-flash", "gemini-3.1-flash-lite", "gemini-2.5-flash", "gemini-2.5-flash-lite"]
locations = ["global", "us-central1", "asia-south1"]

for location in locations:
    client = genai.Client(vertexai=True, project=project, location=location)
    for model in models:
        try:
            reply = client.models.generate_content(model=model, contents="Reply with the single word: ok")
            print(f"OK      {location:12s} {model:24s} -> {reply.text.strip()[:20]!r}")
        except Exception as exc:
            print(f"FAILED  {location:12s} {model:24s} -> {type(exc).__name__}: {str(exc)[:90]}")