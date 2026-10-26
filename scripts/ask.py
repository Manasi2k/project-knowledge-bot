import sys

from kb.answer import answer
from kb.config import load_nextcloud_settings

question = " ".join(sys.argv[1:])
text, sources = answer(question, load_nextcloud_settings().base_url)
print(text)
print("\nSources retrieved:")
for s in sources:
    print(f"[{s['n']}] {s['path']} ({s['location']}, {s['method']}) distance={s['distance']:.3f}")
    print(f"     {s['url']}")