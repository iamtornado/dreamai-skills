# Cross-platform operational workflow

## Contents

1. Platform and installation
2. Resolve input identifiers
3. Start Web UI safely
4. Configure output
5. Preview and download
6. Validate and troubleshoot
7. Convert EPUB for AI agents

## 1. Platform and installation

Use `py -3` as `PYTHON` on native Windows and `python3` on Linux/WSL. Run commands from the skill directory or use absolute script paths. The Python scripts use only the standard library.

Project-scoped skill location (default):

- Windows: `<PROJECT_ROOT>\.agents\skills\tomato-novel-downloader`
- Linux/WSL: `<PROJECT_ROOT>/.agents/skills/tomato-novel-downloader`

Launch Codex from the project root or one of its descendant directories so repository skill discovery includes this folder. Use `%USERPROFILE%\.agents\skills` on Windows or `~/.agents/skills` on Linux only when user-wide availability is explicitly required.

Install the verified upstream release:

```text
PYTHON scripts/install_release.py --output ABSOLUTE_BINARY_PATH
```

Examples:

```powershell
py -3 scripts/install_release.py --output "C:\Users\me\Tools\TomatoNovelDownloader"
```

```bash
python3 scripts/install_release.py --output "/home/me/tools/tomato-novel-downloader"
```

The installer selects Windows/Linux and x64/ARM64, verifies the release asset's SHA-256 digest, and appends `.exe` on Windows when omitted.

## 2. Resolve input identifiers

Accepted directly:

- `7143038691944959011`
- `https://fanqienovel.com/page/7143038691944959011`
- Upstream-supported `/t/<token>` share links for the download command

Resolve `/reader/` pages before preview or download:

```text
PYTHON scripts/resolve_book_id.py "https://fanqienovel.com/reader/7667210176709018137"
```

The numeric suffix of `/reader/` is an item ID, not a Book ID. The controller also performs this resolution automatically for `preview` and `download`.

## 3. Start Web UI safely

Start the service in a persistent foreground terminal. `tomato_web.py` removes proxy variables only from the child process and sets a loopback bypass for IID registration.

Windows:

```powershell
py -3 scripts/tomato_web.py serve --binary "C:\Users\me\Tools\TomatoNovelDownloader.exe" --data-dir "C:\Users\me\TomatoData"
```

Linux:

```bash
python3 scripts/tomato_web.py serve --binary "/home/me/tools/tomato-novel-downloader" --data-dir "/home/me/.local/share/tomato-data"
```

From a second terminal, require `prewarm_error: null`:

```text
PYTHON scripts/tomato_web.py wait-ready
```

The default base URL is `http://127.0.0.1:18423`. For another port, pass matching `--address 127.0.0.1:PORT` to `serve` and `--base-url http://127.0.0.1:PORT` to every API command. Do not expose a non-loopback address without `--password` and appropriate HTTPS/network controls.

## 4. Configure output

Use the controller instead of editing YAML with platform-specific shell tools. It fetches the full live config, changes only deterministic output fields, disables automatic opening, preserves download cache, and persists the result.

```text
PYTHON scripts/tomato_web.py configure --format epub --save-path ABSOLUTE_OUTPUT_DIRECTORY
```

Formats:

| Desired output | `--format` |
| --- | --- |
| EPUB | `epub` |
| One TXT | `txt` |
| PDF | `pdf` |
| One TXT per chapter | `bulk-txt` |

Prefer `epub` as the canonical source for subsequent Markdown conversion.

## 5. Preview and download

Preview without `curl` or `jq`:

```text
PYTHON scripts/tomato_web.py preview "BOOK_ID_OR_PAGE_OR_READER_URL"
```

Create a full-book job and wait for completion:

```text
PYTHON scripts/tomato_web.py download "BOOK_ID_OR_URL"
```

Download a chapter range:

```text
PYTHON scripts/tomato_web.py download "BOOK_ID_OR_URL" --range-start 1 --range-end 10
```

List all jobs:

```text
PYTHON scripts/tomato_web.py jobs --all
```

Only one queued/running job is allowed. A `done` job can still contain placeholder failures during finalization, so validate the saved artifact afterward.

## 6. Validate and troubleshoot

```text
PYTHON scripts/verify_output.py ABSOLUTE_BOOK_EPUB --expected-chapters 1496
```

Failure routing:

| Symptom | Action |
| --- | --- |
| `prewarm_error` mentions IID or `log.snssdk.com` | Confirm the service was started through `tomato_web.py serve`; check DNS, ad-blocking, firewall, and direct HTTPS access |
| `/reader/…` is rejected | Resolve the embedded Book ID with `resolve_book_id.py`; never use the item ID as the Book ID |
| Preview works,正文 fails at `init FanqieClient` | Inspect IID prewarm and runtime logs; web directory fallback is not proof正文 API works |
| Split file contains `[本章下载失败]` | Mark failed even if job state is `done`; retry later or use validated EPUB |
| Windows reports access denied | Keep tools, data, and output in user-writable absolute paths; grant the Codex sandbox access to directories outside the workspace when necessary |
| Public source build lacks Official API crate | Use the verified release binary or the documented no-official build with a user-supplied API pool |

## 7. Convert EPUB for AI agents

Use the validated EPUB rather than split TXT as the canonical conversion input. The converter follows the OPF spine and verifies that every `chapter_*.xhtml` document produces non-empty Markdown.

Long novels must be split into one Markdown file per chapter:

```text
PYTHON scripts/epub_to_markdown.py ABSOLUTE_BOOK_EPUB --type novel --output ABSOLUTE_CHAPTER_DIRECTORY
```

Short stories must remain in one Markdown file, even if their EPUB contains multiple story documents:

```text
PYTHON scripts/epub_to_markdown.py ABSOLUTE_STORY_EPUB --type story --output ABSOLUTE_STORY_MARKDOWN
```

The long-novel output directory must be absent or empty to prevent accidental overwrites. For a short-story file, pass `--overwrite` only when replacing that exact Markdown output is intended.
