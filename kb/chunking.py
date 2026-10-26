import os

from langchain_text_splitters import Language, RecursiveCharacterTextSplitter

from kb.extraction import ExtractionResult

CHUNK_SIZE, CHUNK_OVERLAP = 1000, 150

_plain = RecursiveCharacterTextSplitter(chunk_size=CHUNK_SIZE, chunk_overlap=CHUNK_OVERLAP)
_python = RecursiveCharacterTextSplitter.from_language(
    Language.PYTHON, chunk_size=CHUNK_SIZE, chunk_overlap=CHUNK_OVERLAP)
_markdown = RecursiveCharacterTextSplitter.from_language(
    Language.MARKDOWN, chunk_size=CHUNK_SIZE, chunk_overlap=CHUNK_OVERLAP)


def _splitter(filename: str):
    ext = os.path.splitext(filename)[1].lower()
    return {".py": _python, ".md": _markdown}.get(ext, _plain)


def chunk_file(entry, result: ExtractionResult):
    """Turn one extracted file into (texts, metadatas, ids) ready for the vector store."""
    project_id = entry.path.split("/")[1]
    folder_path = entry.path.rsplit("/", 1)[0]
    splitter = _splitter(entry.name)
    texts, metas, ids = [], [], []
    for seg_i, seg in enumerate(result.segments):
        if not seg.text.strip():
            continue
        header = f"{project_id} | {entry.name} | {seg.location}"
        for chunk_i, piece in enumerate(splitter.split_text(seg.text)):
            texts.append(f"{header}\n{piece}")
            metas.append({
                "file_id": entry.file_id or "",
                "path": entry.path,
                "filename": entry.name,
                "project_id": project_id,
                "folder_path": folder_path,
                "location": seg.location,
                "method": seg.method,
                "etag": entry.etag or "",
                "modified": entry.modified or "",
                "segment": seg_i,
                "chunk": chunk_i,
            })
            ids.append(f"{entry.file_id}-{seg_i}-{chunk_i}")
    return texts, metas, ids