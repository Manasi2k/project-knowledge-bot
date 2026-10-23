import io
import os
import sys

import numpy as np
import pymupdf
import pytesseract
from PIL import Image

from kb.config import load_nextcloud_settings
from kb.nextcloud_client import NextcloudClient

if os.getenv("TESSERACT_CMD"):
    pytesseract.pytesseract.tesseract_cmd = os.getenv("TESSERACT_CMD")

path = sys.argv[1]
data = NextcloudClient(load_nextcloud_settings()).download(path)


def remove_grid_lines(img: Image.Image) -> Image.Image:
    a = np.array(img.convert("L"))
    dark = a < 128
    hrows = np.where(dark.mean(axis=1) > 0.3)[0]      # long horizontal lines
    if len(hrows):
        top, bottom = hrows.min(), hrows.max() + 1
        vcols = np.where(dark[top:bottom].mean(axis=0) > 0.6)[0]  # vertical lines
        a[hrows, :] = 255
        for c in vcols:
            a[top:bottom, c] = 255
    return Image.fromarray(a)


def ocr(img: Image.Image) -> str:
    return pytesseract.image_to_string(remove_grid_lines(img), config="--psm 6").strip()


if path.lower().endswith(".pdf"):
    for i, page in enumerate(pymupdf.open(stream=data, filetype="pdf"), 1):
        text = page.get_text().strip()
        if len(text) >= 20:
            print(f"page {i}: text layer, {len(text)} chars (no OCR needed)")
        else:
            pix = page.get_pixmap(dpi=200)
            out = ocr(Image.open(io.BytesIO(pix.tobytes("png"))))
            print(f"page {i}: OCR, {len(out)} chars\n{out}")
else:
    out = ocr(Image.open(io.BytesIO(data)))
    print(f"image OCR, {len(out)} chars\n{out}")