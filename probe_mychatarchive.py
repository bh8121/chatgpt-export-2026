"""Show what MyChatArchive's CURRENT ChatGPT parser does with the synthetic export.

Run on your own machine (not against real data):
  pip install git+https://github.com/1ch1n/mychatarchive
  python make_chatgpt_fixture.py fx
  python probe_mychatarchive.py fx
  mychatarchive import fx --db /tmp/t.db     # end-to-end: aborts on conv-nullmap

All data is synthetic.
"""
import sys
import traceback
from pathlib import Path

from mychatarchive.parsers import chatgpt, detect_format

fx = Path(sys.argv[1])

print("## detect_format per file")
for f in sorted(fx.iterdir()):
    fmt = detect_format(f) if f.suffix == ".json" else "(not .json; never considered)"
    print(f"{f.name:40s} -> {fmt}")

for shard in sorted(fx.glob("conversations-*.json")):
    print(f"\n## chatgpt.parse({shard.name})")
    try:
        for m in chatgpt.parse(str(shard)):
            print(f"{m['thread_id']:17s} {m['role']:9s} t+{m['created_at'] - 1735689600:>4.0f}  "
                  f"{m['content']!r}")
    except Exception:
        print("EXCEPTION (rest of this shard not parsed):")
        print(traceback.format_exc(limit=2))
