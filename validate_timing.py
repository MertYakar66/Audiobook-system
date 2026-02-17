import json, sys
from pathlib import Path

path = Path("output/readalong/preface-to-the-fourth-edition-by-warren-e-buffett/timing.json")
if not path.exists():
    print(f"FAIL: {path} not found")
    sys.exit(1)

d = json.load(open(path, encoding="utf-8"))
print(f"Chapters: {len(d['chapters'])}")
print(f"Total duration: {d['totalDuration']:.1f}s ({d['totalDuration']/3600:.1f}h)")
print()

for ch in d["chapters"]:
    entries = ch["entries"]
    first = entries[0] if entries else None
    last = entries[-1] if entries else None
    print(f"  {ch['chapterId']}: {ch['title'][:50]:50s} | {len(entries):4d} entries | {ch['duration']:8.1f}s | first_end={first['end'] if first else 'N/A'}")

print()
first_end = d["chapters"][0]["entries"][0]["end"]
if first_end > 0:
    print("TIMESTAMPS: OK (real timestamps detected)")
else:
    print("TIMESTAMPS: FAIL (all zeros)")
