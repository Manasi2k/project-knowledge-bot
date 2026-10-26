"""Format-specific text extraction. Every file returns text plus an honest status."""
import io
import os
from dataclasses import dataclass, field

import numpy as np
import pytesseract
from dotenv import load_dotenv
from PIL import Image

load_dotenv()
if os.getenv("TESSERACT_CMD"):
    pytesseract.pytesseract.tesseract_cmd = os.getenv("TESSERACT_CMD")

MIN_TEXT_CHARS = 20      # below this, a PDF page is treated as scanned
MAX_SHEET_ROWS = 500     # rows of a sheet turned into searchable text


@dataclass
class Segment:
    text: str
    location: str        # "page 2", "slide 4", "sheet Revenue", "body"
    method: str          # "text" or "ocr"


@dataclass
class ExtractionResult:
    segments: list[Segment] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)   # content we could not read
    error: str = ""                                   # extraction crashed
    skipped: str = ""                                 # file type not supported

    @property
    def status(self) -> str:
        if self.error:
            return "failed"
        if self.skipped:
            return "skipped"
        if not any(s.text.strip() for s in self.segments):
            return "empty"
        return "partial" if self.notes else "ok"


def _row(values) -> str:
    return " | ".join("" if v is None else str(v) for v in values)


def _num(v) -> str:
    return str(int(v)) if float(v).is_integer() else str(v)


def _remove_grid_lines(img: Image.Image) -> Image.Image:
    a = np.array(img.convert("L"))
    dark = a < 128
    hrows = np.where(dark.mean(axis=1) > 0.3)[0]
    if len(hrows):
        top, bottom = hrows.min(), hrows.max() + 1
        for c in np.where(dark[top:bottom].mean(axis=0) > 0.6)[0]:
            a[top:bottom, c] = 255
        a[hrows, :] = 255
    return Image.fromarray(a)


def _ocr(img: Image.Image) -> str:
    return pytesseract.image_to_string(_remove_grid_lines(img), config="--psm 6").strip()


def _ocr_bytes(blob: bytes) -> str:
    """OCR an embedded image. Tiny images (icons, bullets) and unreadable formats give ''."""
    try:
        img = Image.open(io.BytesIO(blob))
        if min(img.size) < 100:
            return ""
        return _ocr(img)
    except Exception:
        return ""


def _pdf(data: bytes, res: ExtractionResult) -> None:
    import pymupdf
    pdf = pymupdf.open(stream=data, filetype="pdf")
    for n, page in enumerate(pdf, 1):
        text = page.get_text().strip()
        if len(text) >= MIN_TEXT_CHARS:
            res.segments.append(Segment(text, f"page {n}", "text"))
            for k, img in enumerate(page.get_images(full=True), 1):
                info = pdf.extract_image(img[0])
                out = _ocr_bytes(info["image"]) if info else ""
                if out:
                    res.segments.append(Segment(out, f"page {n} image {k}", "ocr"))
                else:
                    res.notes.append(f"page {n} image {k}: no text found")
        else:
            pix = page.get_pixmap(dpi=200)
            out = _ocr(Image.open(io.BytesIO(pix.tobytes("png"))))
            if out:
                res.segments.append(Segment(out, f"page {n}", "ocr"))
            else:
                res.notes.append(f"page {n}: no text found even with OCR")


def _docx(data: bytes, res: ExtractionResult) -> None:
    from docx import Document
    doc = Document(io.BytesIO(data))
    body = "\n".join(p.text for p in doc.paragraphs if p.text.strip())
    if body:
        res.segments.append(Segment(body, "body", "text"))
    for i, table in enumerate(doc.tables, 1):
        rows = "\n".join(_row(c.text for c in r.cells) for r in table.rows)
        res.segments.append(Segment(rows, f"table {i}", "text"))
    blobs = [r.target_part.blob for r in doc.part.rels.values()
             if "image" in r.reltype and not r.is_external]
    for k, blob in enumerate(blobs, 1):
        out = _ocr_bytes(blob)
        if out:
            res.segments.append(Segment(out, f"embedded image {k}", "ocr"))
        else:
            res.notes.append(f"embedded image {k}: no text found")


def _xlsx(data: bytes, res: ExtractionResult) -> None:
    from openpyxl import load_workbook
    wb = load_workbook(io.BytesIO(data), data_only=True)
    for ws in wb.worksheets:
        rows = []
        for i, row in enumerate(ws.iter_rows(values_only=True)):
            if i >= MAX_SHEET_ROWS:
                res.notes.append(f"sheet {ws.title}: only first {MAX_SHEET_ROWS} rows used")
                break
            if any(v is not None for v in row):
                rows.append(_row(row))
        if rows:
            res.segments.append(Segment("\n".join(rows), f"sheet {ws.title}", "text"))
        if ws._charts:
            res.notes.append(f"sheet {ws.title}: {len(ws._charts)} chart(s) not read")


def _pptx(data: bytes, res: ExtractionResult) -> None:
    from pptx import Presentation
    from pptx.enum.shapes import MSO_SHAPE_TYPE
    for n, slide in enumerate(Presentation(io.BytesIO(data)).slides, 1):
        parts, pictures = [], 0
        for sh in slide.shapes:
            if sh.has_table:
                parts.append("\n".join(_row(c.text for c in r.cells) for r in sh.table.rows))
            elif sh.has_chart:
                plot = sh.chart.plots[0]
                pairs = ", ".join(f"{c}={_num(v)}" for c, v in zip(plot.categories, plot.series[0].values))
                parts.append("Chart: " + pairs)
            elif sh.shape_type == MSO_SHAPE_TYPE.PICTURE:
                out = _ocr_bytes(sh.image.blob)
                if out:
                    res.segments.append(Segment(out, f"slide {n} picture", "ocr"))
                else:
                    pictures += 1
            elif sh.has_text_frame and sh.text_frame.text.strip():
                parts.append(sh.text_frame.text.strip())
        if slide.has_notes_slide and slide.notes_slide.notes_text_frame.text.strip():
            parts.append("Speaker notes: " + slide.notes_slide.notes_text_frame.text.strip())
        if parts:
            res.segments.append(Segment("\n".join(parts), f"slide {n}", "text"))
        if pictures:
            res.notes.append(f"slide {n}: {pictures} picture(s) with no readable text")


def _text(data: bytes, res: ExtractionResult) -> None:
    try:
        res.segments.append(Segment(data.decode("utf-8"), "body", "text"))
    except UnicodeDecodeError:
        res.error = "file is not valid UTF-8"


def _image(data: bytes, res: ExtractionResult) -> None:
    out = _ocr(Image.open(io.BytesIO(data)))
    if out:
        res.segments.append(Segment(out, "image", "ocr"))
    else:
        res.notes.append("no text found by OCR")


HANDLERS = {
    ".pdf": _pdf, ".docx": _docx, ".xlsx": _xlsx, ".pptx": _pptx,
    ".txt": _text, ".md": _text, ".csv": _text, ".json": _text, ".py": _text,
    ".png": _image, ".jpg": _image, ".jpeg": _image,
}


def extract(filename: str, data: bytes) -> ExtractionResult:
    """Extract text from one file. Never raises: problems go into the result."""
    res = ExtractionResult()
    ext = os.path.splitext(filename)[1].lower()
    handler = HANDLERS.get(ext)
    if handler is None:
        res.skipped = f"unsupported file type {ext or '(none)'}"
        return res
    try:
        handler(data, res)
    except Exception as exc:  # report, don't hide
        res.error = f"{type(exc).__name__}: {exc}"
    return res