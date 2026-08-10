---
name: tomato-novel-downloader
description: Install, run, automate, and troubleshoot zhongbai2333/Tomato-Novel-Downloader on native Windows or Linux; download Fanqie/Tomato novels and short stories; convert validated EPUB files into AI-friendly Markdown; and write or verify unified work metadata. Use when a user provides a fanqienovel.com page/reader/share URL or Book ID; asks to download or update a book, resolve a reader item ID, choose or validate an output format, make chapter-per-file Markdown for a long novel, make one Markdown file for a short story, preserve source URL and word count, run the Web UI, migrate the skill between Windows and Linux, or diagnose IID/proxy/API failures. 中文触发：番茄小说下载、短故事下载、Windows/Linux 跨平台、reader 转 Book ID、长篇分章 Markdown、短故事单个 Markdown、作品元数据、原始 URL、总字数、下载完整性检查。
---

# Tomato Novel Downloader

Use the upstream release binary from <https://github.com/zhongbai2333/Tomato-Novel-Downloader>. The public checkout's default build depends on a private `Tomato-Novel-Official-API` crate, so do not assume a source build matches the published binary. Run bundled Python scripts with `py -3` on native Windows and `python3` on Linux/WSL.

## Required workflow

1. Choose a persistent output directory. Keep test artifacts temporary unless the user asks to retain them.
2. Normalize the input:
   - Plain numeric input and `/page/<id>` URLs contain a Book ID.
   - `/reader/<itemId>` contains a chapter/item ID, not a Book ID. Run `scripts/resolve_book_id.py '<URL>'` to extract the page's embedded Book ID.
   - Let the upstream application resolve supported `/t/<token>` share links.
3. Install or update the official release binary only when needed. Run `scripts/install_release.py --output <absolute-binary-path>`; it selects Linux/Windows and x64/ARM64, verifies the GitHub Release SHA-256 digest, and adds `.exe` on Windows.
4. Read `references/workflow.md` before starting a server, automating its HTTP API, changing format, or diagnosing a failure. Use `scripts/tomato_web.py`; do not rewrite its operations as Bash-only `env -u` or `curl | jq` commands.
5. Start the downloader through `tomato_web.py serve`. It removes proxy variables only from the child process because IID registration needs direct access to `log.snssdk.com`; a proxy can make directory preview succeed through web fallback while正文 download still fails.
6. Save the preview evidence with `tomato_web.py preview ... --output <work-root>/source/<book-id>/preview.json`, then validate the produced EPUB with `scripts/verify_output.py`. Never treat Web UI job state `done` alone as proof of success.
7. For AI-agent reading, download and validate EPUB first, then run `scripts/epub_to_markdown.py`. Use `--type novel` for a long novel and `--type story` for a short story; never infer the type from chapter count.
8. Run `scripts/write_work_metadata.py` after validation and conversion to create `<work-root>/metadata.json`, then run it again with `--check`. Preserve the exact input URL, canonical page URL, platform word count, verified chapter counts, artifact paths, and hashes.

## Output selection

Configure the live server with `scripts/tomato_web.py configure --format <value> --save-path <absolute-directory>`:

| Desired output | `--format` |
| --- | --- |
| EPUB | `epub` |
| One TXT | `txt` |
| PDF | `pdf` |
| One TXT per chapter | `bulk-txt` |

The controller disables post-download format questions and automatic file opening, preserves the cache, and persists the absolute save path. Prefer EPUB for the AI-readable Markdown workflow.

Chapter-per-file output is a book-named directory containing `0000_书籍信息.txt` and zero-padded chapter files such as `0001_第1章….txt`.

## AI-readable Markdown

Prefer EPUB as the validated source and post-process it in OPF spine order. Select the platform's Python launcher automatically; the examples below show Linux:

```bash
# Long novel: required chapter-per-file Markdown directory.
python3 scripts/epub_to_markdown.py "/absolute/path/长篇小说.epub" --type novel --output "/absolute/output/长篇小说-分章Markdown"

# Short story: required single Markdown file, even if the EPUB has multiple documents.
python3 scripts/epub_to_markdown.py "/absolute/path/短故事.epub" --type story --output "/absolute/output/短故事.md"
```

Long-novel output contains `0000_书籍信息.md`, `目录.md`, and numbered chapter files such as `0001_第1章….md`. Require the Markdown chapter count to equal the EPUB `chapter_*.xhtml` count. Short-story output contains YAML metadata followed by all story documents in one UTF-8 Markdown file.

Choose the type from the user's intent or original input context: normally `/page/` is a long-novel workflow and `/reader/` is a short-story workflow. If the distinction is unknown, ask; do not guess from how many EPUB documents exist. Do not use upstream split-TXT mode as the source for Markdown when a valid EPUB is available.

## Unified work metadata

Keep one `metadata.json` at the root of every downloaded work, regardless of whether it is a novel or short story. Generate it only after EPUB validation and Markdown conversion:

```text
PYTHON scripts/write_work_metadata.py --type novel --source-url SOURCE_URL --preview-json PREVIEW_JSON --status-json STATUS_JSON --epub BOOK_EPUB --markdown MARKDOWN_OUTPUT --output WORK_ROOT/metadata.json
PYTHON scripts/write_work_metadata.py --check WORK_ROOT/metadata.json
```

The writer cross-checks preview, cache, EPUB, and Markdown evidence. It refuses mismatched Book IDs, titles, authors, word/chapter counts, incomplete caches, corrupt EPUBs, non-contiguous novel chapters, failure markers, paths outside the work root, and accidental metadata overwrite. Use `--overwrite` only to refresh the exact work metadata after its artifacts change.

## Platform rules

- Treat this as a project-scoped skill by default. Copy the complete folder to `<PROJECT_ROOT>/.agents/skills/tomato-novel-downloader`; Codex discovers it when launched from that repository or a descendant directory.
- Native Windows project path: `<PROJECT_ROOT>\.agents\skills\tomato-novel-downloader`. Invoke scripts with `py -3`, use absolute Windows paths, and keep the downloader filename ending in `.exe`.
- Linux/WSL project path: `<PROJECT_ROOT>/.agents/skills/tomato-novel-downloader`. Invoke scripts with `python3` and use absolute POSIX paths.
- Use `%USERPROFILE%\.agents\skills` on Windows or `~/.agents/skills` on Linux only when the user explicitly wants user-wide availability across projects.
- Keep all controller commands on one line when practical. Do not rely on Bash `\` continuation in PowerShell or PowerShell backticks in Bash.
- Use a persistent terminal/session for the foreground `tomato_web.py serve` process, then run `wait-ready`, `configure`, `preview`, and `download` from another terminal/session.
- Default to `127.0.0.1`. Require `--password` before binding the Web UI to a non-loopback address.

## Validation gates

- EPUB: require a valid ZIP container, no failing member, and the expected number of `OEBPS/chapter_*.xhtml` files.
- Split TXT: require the expected chapter count excluding `0000_书籍信息.txt`, no empty chapter file, and no `[本章下载失败]` marker.
- Cache: when available, check `status.json` downloaded entries against the directory chapter count.
- Metadata: require `metadata.json` to pass `write_work_metadata.py --check`; treat `word_count` as the platform-reported value and preserve its evidence source rather than recomputing it from Markdown characters.
- If a short story succeeds as EPUB but split TXT contains `[本章下载失败]`, report the split-mode upstream `register_key` failure; retain the valid EPUB and do not call the split download successful.

Example:

```bash
python3 scripts/verify_output.py "/absolute/path/十日终焉" --expected-chapters 1496
python3 scripts/verify_output.py "/absolute/path/十日终焉.epub" --expected-chapters 1496
```

## Known behavior

- Login and browser cookies are not required. The published official-API build registers an anonymous device IID.
- Direct `/reader/` input is rejected; resolve its embedded Book ID first.
- Release v2.4.13 was verified with a 1496-chapter book in EPUB and split-TXT modes.
- Short-story EPUB worked in testing. Short-story split TXT can fail independently even when the Web UI reports `done`; validation is mandatory.
