import ast
import io
import json
import sys

import pandas as pd

from kb.config import load_nextcloud_settings
from kb.nextcloud_client import NextcloudClient

path = sys.argv[1]
raw = NextcloudClient(load_nextcloud_settings()).download(path)
try:
    text = raw.decode("utf-8")
except UnicodeDecodeError:
    sys.exit("NOT UTF-8: this file would need a different decoder")

ext = path.rsplit(".", 1)[-1].lower()
print(f"{path.rsplit('/', 1)[-1]}: {len(text.split())} words")
if ext == "md":
    print("level-2 headings:", sum(1 for l in text.splitlines() if l.startswith("## ")))
elif ext == "py":
    nodes = list(ast.walk(ast.parse(text)))
    print("classes:", [n.name for n in nodes if isinstance(n, ast.ClassDef)])
    print("functions:", [n.name for n in nodes if isinstance(n, ast.FunctionDef)])
elif ext == "json":
    data = json.loads(text)
    print("keys:", list(data), "| events:", len(data["events"]))
elif ext == "csv":
    df = pd.read_csv(io.StringIO(text))
    print("shape:", df.shape, "| columns:", list(df.columns))