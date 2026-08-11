#!/usr/bin/env python3
"""Write or validate one unified metadata.json for a downloaded Fanqie work."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse
from xml.etree import ElementTree as ET

from verify_output import FAILURE_MARKERS, validate_epub


SCHEMA_VERSION = 1
PAGE_HOSTS = {"fanqienovel.com", "www.fanqienovel.com"}
CHAPTER_MARKDOWN_RE = re.compile(r"^(\d+)_.*\.md$", re.IGNORECASE)
COUNTABLE_CHARACTER_RE = re.compile(
    r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaffA-Za-z0-9]"
)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def timestamp_utc(value: float) -> str:
    return datetime.fromtimestamp(value, timezone.utc).isoformat().replace("+00:00", "Z")


def load_json(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON 根节点必须是对象：{path}")
    return value


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_tree(paths: list[Path], root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(paths, key=lambda item: item.relative_to(root).as_posix()):
        digest.update(path.relative_to(root).as_posix().encode("utf-8"))
        digest.update(b"\0")
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        digest.update(b"\0")
    return digest.hexdigest()


def local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def read_epub_metadata(path: Path) -> dict[str, object]:
    with zipfile.ZipFile(path) as archive:
        container = ET.fromstring(archive.read("META-INF/container.xml"))
        rootfile = next(
            (
                element
                for element in container.iter()
                if local_name(element.tag) == "rootfile"
            ),
            None,
        )
        if rootfile is None or not rootfile.attrib.get("full-path"):
            raise ValueError("EPUB container.xml 缺少 OPF rootfile")
        package = ET.fromstring(archive.read(rootfile.attrib["full-path"]))

    result: dict[str, object] = {"creators": []}
    for element in package.iter():
        name = local_name(element.tag)
        value = "".join(element.itertext()).strip()
        if name == "title" and value and "title" not in result:
            result["title"] = value
        elif name == "creator" and value:
            creators = result["creators"]
            assert isinstance(creators, list)
            creators.append(value)
        elif name == "identifier" and value and "identifier" not in result:
            result["identifier"] = value
        elif name == "description" and value and "description" not in result:
            result["description"] = value
    return result


def normalize_tags(value: object) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str):
        return [item.strip() for item in re.split(r"[|,，]", value) if item.strip()]
    return []


def positive_int(value: object, label: str) -> int:
    if isinstance(value, bool):
        raise ValueError(f"{label} 必须是正整数")
    try:
        number = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{label} 必须是正整数") from exc
    if number <= 0:
        raise ValueError(f"{label} 必须是正整数")
    return number


def choose_equal(label: str, *values: object) -> object:
    present = [value for value in values if value not in (None, "")]
    if not present:
        return None
    normalized = {str(value) for value in present}
    if len(normalized) != 1:
        raise ValueError(f"{label} 来源不一致：{present}")
    return present[0]


def canonicalize_source(source_url: str, book_id: str) -> tuple[str, str]:
    canonical = f"https://fanqienovel.com/page/{book_id}"
    value = source_url.strip()
    if value.isdigit():
        if value != book_id:
            raise ValueError(f"输入 Book ID {value} 与缓存 {book_id} 不一致")
        return canonical, canonical

    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or parsed.hostname not in PAGE_HOSTS:
        raise ValueError("source_url 必须是 fanqienovel.com 的 http(s) URL 或 Book ID")
    match = re.fullmatch(r"/page/(\d+)/?", parsed.path)
    if match and match.group(1) != book_id:
        raise ValueError(f"source_url 的 Book ID {match.group(1)} 与缓存 {book_id} 不一致")
    return value, canonical


def ensure_inside(path: Path, root: Path, label: str) -> str:
    resolved = path.expanduser().resolve()
    try:
        relative = resolved.relative_to(root)
    except ValueError as exc:
        raise ValueError(f"{label} 必须位于作品目录 {root} 内：{resolved}") from exc
    return relative.as_posix()


def require_clean_epub(path: Path, expected_chapters: int) -> dict:
    result = validate_epub(path)
    failures: list[str] = []
    if result["chapter_count"] != expected_chapters:
        failures.append(
            f"EPUB 章节数 {result['chapter_count']} != 预期 {expected_chapters}"
        )
    if result["empty_chapters"]:
        failures.append(f"EPUB 有 {len(result['empty_chapters'])} 个空章")
    if result["failure_marker_chapters"]:
        failures.append(
            f"EPUB 有 {len(result['failure_marker_chapters'])} 个失败标记章节"
        )
    if result.get("bad_zip_member"):
        failures.append(f"EPUB ZIP 损坏成员：{result['bad_zip_member']}")
    if failures:
        raise ValueError("；".join(failures))
    return result


def contains_failure(path: Path) -> bool:
    text = path.read_text(encoding="utf-8", errors="ignore")
    return any(marker in text for marker in FAILURE_MARKERS)


def validate_markdown(
    work_type: str, path: Path, expected_chapters: int
) -> dict[str, object]:
    if work_type == "novel":
        if not path.is_dir():
            raise ValueError(f"长篇 Markdown 必须是目录：{path}")
        markdown_files = sorted(path.glob("*.md"))
        chapters: list[tuple[int, Path]] = []
        for item in markdown_files:
            match = CHAPTER_MARKDOWN_RE.fullmatch(item.name)
            if match and int(match.group(1)) != 0:
                chapters.append((int(match.group(1)), item))
        numbers = [number for number, _ in chapters]
        if numbers != list(range(1, expected_chapters + 1)):
            raise ValueError("长篇 Markdown 章节编号不连续或数量不符")
        if not (path / "0000_书籍信息.md").is_file() or not (path / "目录.md").is_file():
            raise ValueError("长篇 Markdown 缺少 0000_书籍信息.md 或目录.md")
        empty = [item.name for _, item in chapters if not item.read_bytes().strip()]
        markers = [item.name for _, item in chapters if contains_failure(item)]
        if empty:
            raise ValueError(f"长篇 Markdown 有 {len(empty)} 个空章")
        if markers:
            raise ValueError(f"长篇 Markdown 有 {len(markers)} 个失败标记章节")
        return {
            "kind": "directory",
            "chapter_count": len(chapters),
            "file_count": len(markdown_files),
            "sha256_tree": sha256_tree(markdown_files, path),
        }

    if not path.is_file():
        raise ValueError(f"短故事 Markdown 必须是单个文件：{path}")
    if not path.read_bytes().strip():
        raise ValueError("短故事 Markdown 为空")
    if contains_failure(path):
        raise ValueError("短故事 Markdown 包含下载失败标记")
    return {
        "kind": "file",
        "file_count": 1,
        "source_document_count": expected_chapters,
        "bytes": path.stat().st_size,
        "sha256": sha256_file(path),
    }


def count_markdown_characters(work_type: str, path: Path) -> int:
    """Count CJK characters and ASCII letters/digits in downloaded Markdown."""
    if work_type == "novel":
        candidates = []
        for item in sorted(path.glob("*.md")):
            match = CHAPTER_MARKDOWN_RE.fullmatch(item.name)
            if match and int(match.group(1)) != 0:
                candidates.append(item)
    else:
        candidates = [path]
    count = sum(
        len(COUNTABLE_CHARACTER_RE.findall(item.read_text(encoding="utf-8")))
        for item in candidates
    )
    return positive_int(count, "Markdown 可计数字符数")


def preview_parts(snapshot: dict) -> tuple[dict, str | None, str | None]:
    if isinstance(snapshot.get("preview"), dict):
        return (
            snapshot["preview"],
            str(snapshot.get("source_input") or "").strip() or None,
            str(snapshot.get("captured_at") or "").strip() or None,
        )
    return snapshot, None, None


def count_jsonl(path: Path) -> int:
    with path.open("r", encoding="utf-8") as handle:
        return sum(1 for line in handle if line.strip())


def downloaded_count(value: object) -> int:
    if isinstance(value, (list, dict)):
        return len(value)
    raise ValueError("status.json 的 downloaded 必须是数组或对象映射")


def usable_status_chapter_count(status: dict) -> object:
    """Ignore a stale release-cache count only when its own chapter map disproves it."""
    value = status.get("chapter_count")
    try:
        numeric = int(value)
    except (TypeError, ValueError):
        return value
    cache_count = downloaded_count(status.get("downloaded"))
    if cache_count > 0 and numeric != cache_count:
        return None
    return value


def atomic_write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    file_descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    try:
        with os.fdopen(file_descriptor, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(value, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
        os.replace(temporary_name, path)
    except Exception:
        try:
            os.unlink(temporary_name)
        except FileNotFoundError:
            pass
        raise


def build_metadata(args: argparse.Namespace) -> dict:
    output = args.output.expanduser().resolve()
    root = output.parent
    preview_path = args.preview_json.expanduser().resolve()
    status_path = args.status_json.expanduser().resolve()
    epub_path = args.epub.expanduser().resolve()
    markdown_path = args.markdown.expanduser().resolve()
    for path, label in (
        (preview_path, "preview_json"),
        (status_path, "status_json"),
        (epub_path, "epub"),
        (markdown_path, "markdown"),
    ):
        ensure_inside(path, root, label)
        if not path.exists():
            raise ValueError(f"{label} 不存在：{path}")

    preview_snapshot = load_json(preview_path)
    preview, preview_input, preview_captured_at = preview_parts(preview_snapshot)
    status = load_json(status_path)
    epub_metadata = read_epub_metadata(epub_path)

    book_id_value = choose_equal(
        "Book ID",
        preview.get("book_id"),
        status.get("book_id"),
        epub_metadata.get("identifier"),
    )
    if book_id_value is None or not str(book_id_value).isdigit():
        raise ValueError("无法从预览、缓存和 EPUB 得到一致的数字 Book ID")
    book_id = str(book_id_value)

    source_url, canonical_url = canonicalize_source(args.source_url, book_id)
    if preview_input:
        preview_source, _ = canonicalize_source(preview_input, book_id)
        if preview_source != source_url:
            raise ValueError(
                f"source_url 与 preview_json.source_input 不一致：{source_url} != {preview_source}"
            )

    chapter_value = choose_equal(
        "章节数", preview.get("chapter_count"), usable_status_chapter_count(status)
    )
    chapter_count = positive_int(chapter_value, "章节数")
    platform_word_value = choose_equal(
        "总字数", preview.get("word_count"), status.get("word_count")
    )
    if platform_word_value not in (None, ""):
        word_count = positive_int(platform_word_value, "总字数")
        if args.compute_word_count:
            raise ValueError("平台总字数可用时不得使用 --compute-word-count")
        word_count_source = "preview.word_count + status.json.word_count"
    elif args.compute_word_count:
        word_count = count_markdown_characters(args.work_type, markdown_path)
        word_count_source = "computed_from_markdown_countable_characters"
    else:
        raise ValueError("缺少平台总字数；可使用 --compute-word-count 生成透明回退值")

    epub_result = require_clean_epub(epub_path, chapter_count)
    markdown_result = validate_markdown(args.work_type, markdown_path, chapter_count)

    downloaded = status.get("downloaded")
    cache_count = downloaded_count(downloaded)
    if cache_count != chapter_count:
        raise ValueError("status.json 的 downloaded 数量与章节数不一致")
    jsonl_path = status_path.with_name("downloaded_chapters.jsonl")
    if not jsonl_path.is_file():
        raise ValueError(f"缺少下载缓存账本：{jsonl_path}")
    jsonl_count = count_jsonl(jsonl_path)
    if jsonl_count != chapter_count:
        raise ValueError(
            f"downloaded_chapters.jsonl 行数 {jsonl_count} != 章节数 {chapter_count}"
        )

    sourced_title = choose_equal(
        "书名", preview.get("book_name"), status.get("book_name"), epub_metadata.get("title")
    )
    if sourced_title not in (None, "") and args.title:
        choose_equal("书名", sourced_title, args.title)
    title = str(sourced_title or args.title or "").strip()
    if not title:
        raise ValueError("缺少书名")
    creators = epub_metadata.get("creators") or []
    epub_author = creators[0] if isinstance(creators, list) and creators else None
    sourced_author = choose_equal(
        "作者", preview.get("author"), status.get("author"), epub_author
    )
    if sourced_author not in (None, "") and args.author:
        choose_equal("作者", sourced_author, args.author)
    author = str(sourced_author or args.author or "").strip()
    if not author:
        raise ValueError("缺少作者")

    original_title = str(preview.get("original_book_name") or "").strip() or None
    description = str(
        preview.get("description")
        or status.get("description")
        or epub_metadata.get("description")
        or ""
    ).strip()
    tags = normalize_tags(preview.get("tags") or status.get("tags"))

    artifacts: dict[str, object] = {
        "preview_json": {
            "path": ensure_inside(preview_path, root, "preview_json"),
            "sha256": sha256_file(preview_path),
        },
        "status_json": {
            "path": ensure_inside(status_path, root, "status_json"),
            "sha256": sha256_file(status_path),
            "downloaded_count": cache_count,
        },
        "downloaded_chapters_jsonl": {
            "path": ensure_inside(jsonl_path, root, "downloaded_chapters_jsonl"),
            "sha256": sha256_file(jsonl_path),
            "line_count": jsonl_count,
        },
        "epub": {
            "path": ensure_inside(epub_path, root, "epub"),
            "sha256": sha256_file(epub_path),
            "bytes": epub_path.stat().st_size,
            "chapter_count": epub_result["chapter_count"],
        },
        "markdown": {
            "path": ensure_inside(markdown_path, root, "markdown"),
            **markdown_result,
        },
    }

    return {
        "schema_version": SCHEMA_VERSION,
        "work_type": args.work_type,
        "book_id": book_id,
        "title": title,
        "original_title": original_title,
        "author": author,
        "source_url": source_url,
        "canonical_url": canonical_url,
        "chapter_count": chapter_count,
        "word_count": word_count,
        "word_count_source": word_count_source,
        "finished": bool(preview.get("finished", status.get("finished", False))),
        "category": str(preview.get("category") or status.get("category") or "").strip()
        or None,
        "tags": tags,
        "description": description or None,
        "preview_captured_at": preview_captured_at,
        "downloaded_at": timestamp_utc(status_path.stat().st_mtime),
        "downloaded_at_source": "status_json_mtime",
        "verified_at": utc_now(),
        "artifacts": artifacts,
    }


def expect_equal(actual: object, expected: object, label: str) -> None:
    if actual != expected:
        raise ValueError(f"{label} 已漂移：{actual!r} != {expected!r}")


def resolve_artifact(root: Path, item: dict, label: str) -> Path:
    relative = item.get("path")
    if not isinstance(relative, str) or not relative:
        raise ValueError(f"metadata.json 缺少 artifacts.{label}.path")
    candidate = (root / Path(relative)).resolve()
    ensure_inside(candidate, root, f"artifacts.{label}.path")
    if not candidate.exists():
        raise ValueError(f"artifacts.{label}.path 不存在：{candidate}")
    return candidate


def check_metadata(path: Path) -> dict[str, object]:
    metadata_path = path.expanduser().resolve()
    metadata = load_json(metadata_path)
    root = metadata_path.parent
    expect_equal(metadata.get("schema_version"), SCHEMA_VERSION, "schema_version")
    work_type = metadata.get("work_type")
    if work_type not in {"novel", "story"}:
        raise ValueError("work_type 必须是 novel 或 story")
    book_id = str(metadata.get("book_id") or "")
    if not book_id.isdigit():
        raise ValueError("book_id 必须是数字字符串")
    chapter_count = positive_int(metadata.get("chapter_count"), "chapter_count")
    positive_int(metadata.get("word_count"), "word_count")
    if not str(metadata.get("title") or "").strip():
        raise ValueError("metadata.json 缺少 title")
    if not str(metadata.get("author") or "").strip():
        raise ValueError("metadata.json 缺少 author")
    source_url, canonical_url = canonicalize_source(str(metadata.get("source_url") or ""), book_id)
    expect_equal(source_url, metadata.get("source_url"), "source_url")
    expect_equal(canonical_url, metadata.get("canonical_url"), "canonical_url")

    artifacts = metadata.get("artifacts")
    if not isinstance(artifacts, dict):
        raise ValueError("metadata.json 缺少 artifacts")

    preview_item = artifacts.get("preview_json")
    status_item = artifacts.get("status_json")
    jsonl_item = artifacts.get("downloaded_chapters_jsonl")
    epub_item = artifacts.get("epub")
    markdown_item = artifacts.get("markdown")
    for label, item in (
        ("preview_json", preview_item),
        ("status_json", status_item),
        ("downloaded_chapters_jsonl", jsonl_item),
        ("epub", epub_item),
        ("markdown", markdown_item),
    ):
        if not isinstance(item, dict):
            raise ValueError(f"metadata.json 缺少 artifacts.{label}")

    preview_path = resolve_artifact(root, preview_item, "preview_json")
    status_path = resolve_artifact(root, status_item, "status_json")
    jsonl_path = resolve_artifact(root, jsonl_item, "downloaded_chapters_jsonl")
    epub_path = resolve_artifact(root, epub_item, "epub")
    markdown_path = resolve_artifact(root, markdown_item, "markdown")

    expect_equal(sha256_file(preview_path), preview_item.get("sha256"), "preview_json sha256")
    expect_equal(sha256_file(status_path), status_item.get("sha256"), "status_json sha256")
    expect_equal(sha256_file(jsonl_path), jsonl_item.get("sha256"), "JSONL sha256")
    expect_equal(sha256_file(epub_path), epub_item.get("sha256"), "EPUB sha256")
    expect_equal(epub_path.stat().st_size, epub_item.get("bytes"), "EPUB bytes")

    preview, _, _ = preview_parts(load_json(preview_path))
    status = load_json(status_path)
    expect_equal(str(status.get("book_id")), book_id, "status book_id")
    expect_equal(str(preview.get("book_id")), book_id, "preview book_id")
    status_chapters = usable_status_chapter_count(status)
    if status_chapters is not None:
        expect_equal(
            positive_int(status_chapters, "status chapter_count"),
            chapter_count,
            "status chapter_count",
        )
    expect_equal(positive_int(preview.get("chapter_count"), "preview chapter_count"), chapter_count, "preview chapter_count")
    platform_word_value = choose_equal(
        "总字数", preview.get("word_count"), status.get("word_count")
    )
    if platform_word_value not in (None, ""):
        expect_equal(
            positive_int(platform_word_value, "平台总字数"),
            metadata.get("word_count"),
            "platform word_count",
        )
        expect_equal(
            metadata.get("word_count_source"),
            "preview.word_count + status.json.word_count",
            "word_count_source",
        )
    else:
        expect_equal(
            metadata.get("word_count_source"),
            "computed_from_markdown_countable_characters",
            "word_count_source",
        )
        expect_equal(
            count_markdown_characters(str(work_type), markdown_path),
            metadata.get("word_count"),
            "computed word_count",
        )

    cache_count = downloaded_count(status.get("downloaded"))
    expect_equal(cache_count, status_item.get("downloaded_count"), "status downloaded_count")
    expect_equal(cache_count, chapter_count, "status downloaded_count")
    jsonl_count = count_jsonl(jsonl_path)
    expect_equal(jsonl_count, jsonl_item.get("line_count"), "JSONL line_count")
    expect_equal(jsonl_count, chapter_count, "JSONL line_count")

    epub_result = require_clean_epub(epub_path, chapter_count)
    expect_equal(epub_result["chapter_count"], epub_item.get("chapter_count"), "EPUB chapter_count")
    markdown_result = validate_markdown(str(work_type), markdown_path, chapter_count)
    for key, value in markdown_result.items():
        expect_equal(value, markdown_item.get(key), f"Markdown {key}")

    return {
        "ok": True,
        "mode": "check",
        "path": str(metadata_path),
        "book_id": book_id,
        "work_type": work_type,
        "chapter_count": chapter_count,
        "word_count": metadata.get("word_count"),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", type=Path, metavar="METADATA_JSON")
    parser.add_argument("--type", choices=("novel", "story"), dest="work_type")
    parser.add_argument("--source-url")
    parser.add_argument("--preview-json", type=Path)
    parser.add_argument("--status-json", type=Path)
    parser.add_argument("--epub", type=Path)
    parser.add_argument("--markdown", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--title")
    parser.add_argument("--author")
    parser.add_argument("--compute-word-count", action="store_true")
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()
    if args.check:
        supplied = [
            args.work_type,
            args.source_url,
            args.preview_json,
            args.status_json,
            args.epub,
            args.markdown,
            args.output,
            args.title,
            args.author,
            args.compute_word_count,
            args.overwrite,
        ]
        if any(supplied):
            parser.error("--check 不能与生成模式参数同时使用")
        return args

    required = {
        "--type": args.work_type,
        "--source-url": args.source_url,
        "--preview-json": args.preview_json,
        "--status-json": args.status_json,
        "--epub": args.epub,
        "--markdown": args.markdown,
        "--output": args.output,
    }
    missing = [name for name, value in required.items() if value in (None, "")]
    if missing:
        parser.error("生成模式缺少参数：" + ", ".join(missing))
    return args


def main() -> int:
    args = parse_args()
    try:
        if args.check:
            result = check_metadata(args.check)
        else:
            output = args.output.expanduser().resolve()
            if output.exists() and not args.overwrite:
                raise ValueError(f"输出已存在；如需替换请使用 --overwrite：{output}")
            metadata = build_metadata(args)
            atomic_write_json(output, metadata)
            result = {
                "ok": True,
                "mode": "write",
                "path": str(output),
                "book_id": metadata["book_id"],
                "work_type": metadata["work_type"],
                "chapter_count": metadata["chapter_count"],
                "word_count": metadata["word_count"],
            }
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (OSError, ValueError, KeyError, json.JSONDecodeError, zipfile.BadZipFile) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
