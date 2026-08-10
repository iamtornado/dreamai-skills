#!/usr/bin/env python3
"""Validate Tomato-Novel-Downloader EPUB or split-TXT output."""

from __future__ import annotations

import argparse
import json
import re
import sys
import zipfile
from pathlib import Path


CHAPTER_XHTML_RE = re.compile(r"^OEBPS/chapter_\d+\.xhtml$")
FAILURE_MARKERS = (
    "[本章下载失败]",
    "访问太频繁",
    "登录后阅读",
    "打开番茄小说APP",
    "下载番茄小说APP",
)


def contains_failure(data: bytes) -> bool:
    text = data.decode("utf-8", errors="ignore")
    return any(marker in text for marker in FAILURE_MARKERS)


def validate_epub(path: Path) -> dict:
    with zipfile.ZipFile(path) as archive:
        bad_member = archive.testzip()
        chapters = sorted(name for name in archive.namelist() if CHAPTER_XHTML_RE.match(name))
        marker_files = [name for name in chapters if contains_failure(archive.read(name))]
        empty_files = [name for name in chapters if len(archive.read(name)) == 0]
    return {
        "type": "epub",
        "path": str(path.resolve()),
        "chapter_count": len(chapters),
        "empty_chapters": empty_files,
        "failure_marker_chapters": marker_files,
        "bad_zip_member": bad_member,
    }


def validate_split_txt(path: Path) -> dict:
    files = sorted(path.glob("*.txt"))
    metadata = [item for item in files if item.name.startswith("0000_")]
    chapters = [item for item in files if item not in metadata]
    empty_files = [item.name for item in chapters if item.stat().st_size == 0]
    marker_files = [item.name for item in chapters if contains_failure(item.read_bytes())]
    return {
        "type": "split_txt",
        "path": str(path.resolve()),
        "chapter_count": len(chapters),
        "metadata_count": len(metadata),
        "empty_chapters": empty_files,
        "failure_marker_chapters": marker_files,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", type=Path)
    parser.add_argument("--expected-chapters", type=int)
    args = parser.parse_args()

    if not args.path.exists():
        print(json.dumps({"ok": False, "error": "path does not exist"}, ensure_ascii=False))
        return 1

    try:
        if args.path.is_dir():
            result = validate_split_txt(args.path)
        elif args.path.suffix.lower() == ".epub":
            result = validate_epub(args.path)
        else:
            raise ValueError("path must be an EPUB or split-TXT directory")
    except Exception as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False))
        return 1

    failures = []
    if args.expected_chapters is not None and result["chapter_count"] != args.expected_chapters:
        failures.append(
            f"chapter count {result['chapter_count']} != expected {args.expected_chapters}"
        )
    if result["empty_chapters"]:
        failures.append(f"{len(result['empty_chapters'])} empty chapter(s)")
    if result["failure_marker_chapters"]:
        failures.append(f"{len(result['failure_marker_chapters'])} failure marker chapter(s)")
    if result.get("bad_zip_member"):
        failures.append(f"corrupt ZIP member: {result['bad_zip_member']}")

    result["ok"] = not failures
    result["failures"] = failures
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
