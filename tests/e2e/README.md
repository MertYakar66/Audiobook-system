# Scriptum End-to-End Tests

Automated browser tests for the Scriptum reader built with
[Playwright for Python](https://playwright.dev/python/). A single script
(`run_tests.py`) drives headless Chromium through the library page, the
Read & Listen reader, the Read Only reader, and verifies audio↔text
synchronization, highlights, notes, bookmarks, themes, search, sleep timer,
chapter navigation, progress persistence, service worker caching, mobile
viewport rendering, and performance metrics.

## Quick start

```bash
# 1. Install Playwright (one-time)
pip install 'playwright==1.56.0'
python3 -m playwright install chromium

# 2. Generate silent placeholder MP3s (one-time, if audio is missing)
pip install lameenc
python3 tests/e2e/generate_silent_audio.py

# 3. Start the dev server in one terminal
python3 serve.py 8765

# 4. Run the tests in another terminal
python3 tests/e2e/run_tests.py

# Optional: run headed to watch it drive
python3 tests/e2e/run_tests.py --headed
```

Output:
- Screenshots → `tests/e2e/screenshots/`
- Markdown report → `tests/e2e/reports/report.md`

## How audio-sync testing works without real TTS audio

The audio files shipped with the book are large TTS-generated MP3s that live
outside the repo. In environments where only `manifest.json`, `text.json`, and
`timing.json` are present, `generate_silent_audio.py` produces silent MP3s
whose durations match each chapter's timing. Because `reader.js` drives
sentence highlighting from `audio.currentTime`, seeking the silent audio to
known timing positions exercises exactly the same code path as real
playback — any sync regression is caught.

The `Reader: audio→text sync via timeupdate` test seeks to the midpoint of
three known timing entries and asserts that the corresponding
`.sentence.active` element appears in the DOM.

## Tests (29 total)

| Area | Tests |
|------|-------|
| Library | loads, counts, theme light/sepia, search, grid/list, notes section nav |
| Reader audio | metadata, play/pause, sync, sentence-click seek, skip +30/−10, speed, chapter nav |
| Reader content | highlight, note + modal, bookmark + panel, in-book search, sleep timer |
| Reader UX | font size, theme switching, progress persistence, highlights persistence |
| Reader Text | shell loads |
| PWA | service worker, offline reload, mobile viewport, perf metrics |

## Files

- `run_tests.py` — self-contained Playwright test driver + report writer
- `generate_silent_audio.py` — creates per-chapter silent MP3s matching `timing.json`
- `screenshots/` — per-test PNGs (overwritten each run)
- `reports/report.md` — Markdown report (overwritten each run)
