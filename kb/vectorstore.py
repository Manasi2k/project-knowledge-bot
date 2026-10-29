from functools import lru_cache

from langchain_chroma import Chroma
from langchain_huggingface import HuggingFaceEmbeddings

EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
PERSIST_DIR = "chroma_db"
COLLECTION = "project_chunks"


@lru_cache(maxsize=1)
def get_store() -> Chroma:
    return Chroma(
        collection_name=COLLECTION,
        embedding_function=HuggingFaceEmbeddings(model_name=EMBEDDING_MODEL),
        persist_directory=PERSIST_DIR,
    )