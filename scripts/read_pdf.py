import sys

import pymupdf as fitz

from kb.config import load_nextcloud_settings
from kb.nextcloud_client import NextcloudClient

client = NextcloudClient(load_nextcloud_settings())
doc = fitz.open(stream=client.download(sys.argv[1]), filetype="pdf")
for i, page in enumerate(doc, 1):
    text = page.get_text()
    print(f"--- page {i}: {len(text)} characters ---")
    print(text)