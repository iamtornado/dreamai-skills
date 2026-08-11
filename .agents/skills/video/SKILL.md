---
name: video
description: Analyze a video (Loom, YouTube, Vimeo, TikTok, Instagram, X/Twitter, Twitch, Dailymotion, Facebook, direct URL, or local file) — transcript, key frames, OCR text, metadata, annotated timeline — and answer questions about it with timestamps.
argument-hint: "<video-url-or-path> [question]"
allowed-tools: Bash, Read, mcp__video-analyzer
homepage: https://github.com/guimatheus92/mcp-video-analyzer
license: MIT
---

Analyze the given video and answer the user's question (or summarize it if no question was asked). Always cite timestamps (`M:SS`) in your answer.

## Project OCR policy — PaddleOCR

For any request that needs on-screen text or a general visual analysis, use the project wrapper in `scripts/analyze_with_paddleocr.py`. It deliberately runs `mcp-video-analyzer` in `brief` mode, where Tesseract is skipped, then:

1. samples frames uniformly across the full duration with ffmpeg;
2. runs PaddleOCR on the original-resolution frames (GPU `gpu:0` by default);
3. emits resized frames for the agent; and
4. rebuilds the annotated timeline after both Whisper and PaddleOCR finish.

This is a real backend replacement: do not call upstream `analyze_video`/the standard CLI first and then redundantly run PaddleOCR.

Install the project-scoped runtime once if `.venv/bin/python` is absent:

```bash
bash <skill-dir>/scripts/install_paddleocr.sh
```

Run the full analysis:

```bash
<skill-dir>/.venv/bin/python \
  <skill-dir>/scripts/analyze_with_paddleocr.py \
  "<video-url-or-path>" \
  --out "<persistent-output-dir>" \
  --language zh \
  --max-frames 12
```

The JSON on stdout contains `metadata`, `transcript`, `frames`, `ocrResults`, `timeline`, and `warnings`. Progress goes to stderr, and the same document is persisted as `<persistent-output-dir>/analysis.json`. Each frame has an emitted `filePath` and an OCR-resolution `originalFilePath`.

Useful flags: `--device gpu:0|cpu`, `--ocr-language ch|en|...`, `--min-confidence 0.45`, `--max-frames 1..60`, `--max-width 0|<px>`, `--model <Whisper model>`, `--force-refresh`. The wrapper understands local files, `file://`, yt-dlp-supported URLs, and public Fanqie article URLs. `YTDLP_COOKIES` and `YTDLP_COOKIES_FROM_BROWSER` are honored for protected sources.

## Route A — MCP for non-OCR questions

If the `video-analyzer` MCP server is connected, call its tools directly only when PaddleOCR is unnecessary:

- Question answerable from speech alone → `get_transcript` (fast, no frame extraction)
- Title / duration / views / comments only → `get_metadata` (no download)
- A specific visual moment without OCR → `analyze_moment` or `get_frame_at`
- Motion or fast UI changes without OCR → `get_frame_burst`

**Dense UI capture** (terminal, dashboard, IDE, spreadsheet — the meaning is in small text): pass `maxWidth` on any of these tools. Emitted frames are capped at 800 px wide by default, which turns a 1920×1080 screencast into 800×450 and drops a 15 px UI font below what a vision model can read. `maxWidth: 0` keeps the source resolution; a value like `1568` is the middle ground. Native frames cost several times more context, so raise it for the close read, not for the overview.

## Route B — upstream fallback when PaddleOCR cannot run

Only when the project wrapper cannot run, fall back to the one-shot upstream CLI. Its OCR is Tesseract CPU/WASM, so report the degradation:

```bash
npx -y mcp-video-analyzer@latest analyze "<video-url-or-path>"
```

stdout is a single JSON document: `metadata`, `transcript` (timestamped entries), `ocrResults` (on-screen text), `timeline`, `warnings`, and `frames` — an array of `{ time, filePath, mimeType }` pointing to JPEG key frames on disk. Then:

1. Parse the JSON from stdout.
2. Read the `frames[].filePath` images (in parallel) when the question needs visuals.
3. Answer from transcript + OCR + frames, citing timestamps.

Useful flags: `--detail brief|standard|detailed` (brief = metadata + transcript only, no frame extraction — the fast/cheap path), `--fields metadata,transcript` (filters the emitted JSON only; frames are still computed at standard detail), `--max-frames <1-60>`, `--max-width <px>` (frame width cap, default 800; `0` keeps source resolution — use it for dense UI captures whose payload is small text), `--language <code>` (force transcription language), `--out <dir>` (where frames are copied), `--force-refresh`. Run `npx -y mcp-video-analyzer@latest analyze --help` for the full list.

## Prerequisites & degradation

- PaddleOCR route: Python 3.12 project venv, PaddlePaddle GPU, ffmpeg, Node.js 18+, and yt-dlp for web sources. The first OCR run downloads the official detection/recognition models into the skill-local `.cache/` directory.
- Upstream fallback: Node.js 18+; ffmpeg is bundled.
- Platform URLs (YouTube, Instagram, TikTok, …) require `yt-dlp` on PATH; direct `.mp4/.webm/.mov` URLs and local files work without it. Loom transcript, metadata, and comments need no `yt-dlp` either. Loom **frames** usually do — Loom serves most videos as separate DASH video+audio streams that only `yt-dlp` fetches and merges; a CDN fallback covers some videos without it.
- The upstream tool usually reports partial failures in `warnings`, but v0.8.0 can hard-exit when Tesseract language downloads fail. The PaddleOCR wrapper avoids that path. Relay any remaining warnings to the user.
- An empty transcript alongside a "silent audio" warning means the video genuinely has no speech (common for muted Reels/Stories) — that is content, not a failure.
