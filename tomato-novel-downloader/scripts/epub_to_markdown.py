#!/usr/bin/env python3
"""Convert a Tomato Novel Downloader EPUB into AI-friendly Markdown."""

from __future__ import annotations

import argparse
import json
import posixpath
import re
import sys
import zipfile
from html.parser import HTMLParser
from pathlib import Path, PurePosixPath
from urllib.parse import quote, unquote
from xml.etree import ElementTree as ET


CONTAINER_PATH = "META-INF/container.xml"
CHAPTER_RE = re.compile(r"^chapter_\d+\.(?:xhtml|html?)$", re.IGNORECASE)
FAILURE_MARKER = "[本章下载失败]"


def local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def child_elements(parent: ET.Element, name: str):
    for element in parent.iter():
        if local_name(element.tag) == name:
            yield element


class XHTMLToMarkdown(HTMLParser):
    """Small, dependency-free XHTML-to-Markdown converter for novel prose."""

    SKIP_TAGS = {"head", "script", "style", "nav"}
    BLOCK_TAGS = {
        "address",
        "article",
        "aside",
        "div",
        "figure",
        "figcaption",
        "footer",
        "header",
        "main",
        "p",
        "section",
        "table",
        "tr",
    }

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.skip_depth = 0
        self.in_body = False
        self.list_depth = 0
        self.in_pre = False

    def append(self, value: str) -> None:
        if value:
            self.parts.append(value)

    def newline(self, count: int = 1) -> None:
        current = "".join(self.parts[-3:])
        existing = len(current) - len(current.rstrip("\n"))
        if existing < count:
            self.parts.append("\n" * (count - existing))

    def handle_starttag(self, tag: str, attrs) -> None:
        tag = tag.lower()
        attrs_dict = dict(attrs)
        if tag in self.SKIP_TAGS:
            self.skip_depth += 1
            return
        if self.skip_depth:
            return
        if tag == "body":
            self.in_body = True
            return
        if not self.in_body:
            return
        if re.fullmatch(r"h[1-6]", tag):
            self.newline(2)
            self.append("#" * int(tag[1]) + " ")
        elif tag in self.BLOCK_TAGS:
            self.newline(2)
        elif tag == "br":
            self.newline(1)
        elif tag in {"ul", "ol"}:
            self.list_depth += 1
            self.newline(1)
        elif tag == "li":
            self.newline(1)
            self.append("  " * max(0, self.list_depth - 1) + "- ")
        elif tag == "blockquote":
            self.newline(2)
            self.append("> ")
        elif tag in {"strong", "b"}:
            self.append("**")
        elif tag in {"em", "i"}:
            self.append("*")
        elif tag == "code":
            self.append("`")
        elif tag == "pre":
            self.newline(2)
            self.append("```\n")
            self.in_pre = True
        elif tag == "img":
            alt = (attrs_dict.get("alt") or "").strip()
            if alt:
                self.append(f"[插图：{alt}]")

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag in self.SKIP_TAGS:
            if self.skip_depth:
                self.skip_depth -= 1
            return
        if self.skip_depth:
            return
        if tag == "body":
            self.in_body = False
        elif not self.in_body:
            return
        elif re.fullmatch(r"h[1-6]", tag) or tag in self.BLOCK_TAGS:
            self.newline(2)
        elif tag in {"ul", "ol"}:
            self.list_depth = max(0, self.list_depth - 1)
            self.newline(1)
        elif tag == "li":
            self.newline(1)
        elif tag == "blockquote":
            self.newline(2)
        elif tag in {"strong", "b"}:
            self.append("**")
        elif tag in {"em", "i"}:
            self.append("*")
        elif tag == "code":
            self.append("`")
        elif tag == "pre":
            self.append("\n```\n\n")
            self.in_pre = False

    def handle_data(self, data: str) -> None:
        if self.skip_depth or not self.in_body:
            return
        if self.in_pre:
            self.append(data)
            return
        normalized = re.sub(r"\s+", " ", data)
        if not normalized.strip():
            return
        if self.parts and not self.parts[-1].endswith((" ", "\n", "`", "*")):
            if data[:1].isspace():
                self.append(" ")
        self.append(normalized.strip())
        if data[-1:].isspace():
            self.append(" ")

    def markdown(self) -> str:
        text = "".join(self.parts)
        text = re.sub(r"[ \t]+\n", "\n", text)
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip() + "\n"


def xhtml_to_markdown(raw: bytes) -> str:
    parser = XHTMLToMarkdown()
    parser.feed(raw.decode("utf-8", errors="replace"))
    parser.close()
    return parser.markdown()


def epub_contents(epub: Path):
    try:
        archive = zipfile.ZipFile(epub)
    except (OSError, zipfile.BadZipFile) as exc:
        raise ValueError(f"不是有效的 EPUB/ZIP：{exc}") from exc

    with archive:
        bad_member = archive.testzip()
        if bad_member:
            raise ValueError(f"EPUB 中的文件校验失败：{bad_member}")
        try:
            container = ET.fromstring(archive.read(CONTAINER_PATH))
            rootfile = next(child_elements(container, "rootfile"))
            opf_path = rootfile.attrib["full-path"]
            opf = ET.fromstring(archive.read(opf_path))
        except (KeyError, StopIteration, ET.ParseError) as exc:
            raise ValueError(f"无法读取 EPUB 的 container/OPF：{exc}") from exc

        metadata: dict[str, object] = {"creators": []}
        for element in opf.iter():
            name = local_name(element.tag)
            value = "".join(element.itertext()).strip()
            if name == "title" and value and "title" not in metadata:
                metadata["title"] = value
            elif name == "creator" and value:
                metadata["creators"].append(value)
            elif name == "identifier" and value and "identifier" not in metadata:
                metadata["identifier"] = value
            elif name == "description" and value and "description" not in metadata:
                metadata["description"] = value

        manifest: dict[str, dict[str, str]] = {}
        for item in child_elements(opf, "item"):
            item_id = item.attrib.get("id")
            href = item.attrib.get("href")
            if item_id and href:
                manifest[item_id] = {
                    "href": href,
                    "media_type": item.attrib.get("media-type", ""),
                    "properties": item.attrib.get("properties", ""),
                }

        opf_dir = posixpath.dirname(opf_path)
        chapters: list[tuple[str, bytes]] = []
        for itemref in child_elements(opf, "itemref"):
            item = manifest.get(itemref.attrib.get("idref", ""))
            if not item:
                continue
            href = unquote(item["href"].split("#", 1)[0])
            if not CHAPTER_RE.match(PurePosixPath(href).name):
                continue
            member = posixpath.normpath(posixpath.join(opf_dir, href))
            try:
                chapters.append((member, archive.read(member)))
            except KeyError as exc:
                raise ValueError(f"OPF 引用的章节不存在：{member}") from exc

    if not chapters:
        raise ValueError("没有在 EPUB spine 中找到 chapter_*.xhtml 章节")
    return metadata, chapters


def yaml_scalar(value: object) -> str:
    return json.dumps(str(value), ensure_ascii=False)


def metadata_markdown(metadata: dict[str, object], epub: Path) -> str:
    lines = ["---"]
    if metadata.get("title"):
        lines.append(f"title: {yaml_scalar(metadata['title'])}")
    creators = metadata.get("creators") or []
    if creators:
        lines.append("authors:")
        lines.extend(f"  - {yaml_scalar(author)}" for author in creators)
    if metadata.get("identifier"):
        lines.append(f"identifier: {yaml_scalar(metadata['identifier'])}")
    lines.append(f"source_epub: {yaml_scalar(epub.name)}")
    lines.extend(["---", ""])
    return "\n".join(lines)


def chapter_title(markdown: str, fallback: str) -> str:
    for line in markdown.splitlines():
        match = re.match(r"^#{1,6}\s+(.+?)\s*$", line)
        if match:
            return match.group(1).strip()
    return fallback


def safe_filename(value: str, max_length: int = 96) -> str:
    value = re.sub(r"[\x00-\x1f<>:\"/\\|?*]", "_", value)
    value = re.sub(r"\s+", " ", value).strip(" .")
    return (value or "未命名章节")[:max_length].rstrip(" .")


def default_output(epub: Path, content_type: str) -> Path:
    if content_type == "story":
        return epub.with_suffix(".md")
    return epub.with_name(f"{epub.stem}-分章Markdown")


def convert_story(
    epub: Path,
    output: Path,
    metadata: dict[str, object],
    chapters: list[tuple[str, bytes]],
    overwrite: bool,
) -> None:
    if output.exists() and not overwrite:
        raise ValueError(f"输出文件已存在；如需覆盖请加 --overwrite：{output}")
    if output.exists() and not output.is_file():
        raise ValueError(f"短故事输出必须是文件路径：{output}")
    output.parent.mkdir(parents=True, exist_ok=True)
    rendered = [xhtml_to_markdown(raw).strip() for _, raw in chapters]
    if any(not chapter for chapter in rendered):
        raise ValueError("至少一个 EPUB 章节转换后为空")
    body = "\n\n---\n\n".join(rendered) + "\n"
    if FAILURE_MARKER in body:
        raise ValueError(f"正文包含失败标记 {FAILURE_MARKER}")
    output.write_text(metadata_markdown(metadata, epub) + body, encoding="utf-8")


def convert_novel(
    epub: Path,
    output: Path,
    metadata: dict[str, object],
    chapters: list[tuple[str, bytes]],
) -> None:
    if output.exists() and not output.is_dir():
        raise ValueError(f"长篇小说输出必须是目录路径：{output}")
    if output.exists() and any(output.iterdir()):
        raise ValueError(f"输出目录必须不存在或为空，避免覆盖已有文件：{output}")
    output.mkdir(parents=True, exist_ok=True)

    width = max(4, len(str(len(chapters))))
    toc: list[tuple[str, str]] = []
    for index, (member, raw) in enumerate(chapters, start=1):
        markdown = xhtml_to_markdown(raw)
        if not markdown.strip():
            raise ValueError(f"章节转换后为空：{member}")
        if FAILURE_MARKER in markdown:
            raise ValueError(f"章节包含失败标记 {FAILURE_MARKER}：{member}")
        title = chapter_title(markdown, f"第{index}章")
        filename = f"{index:0{width}d}_{safe_filename(title)}.md"
        (output / filename).write_text(markdown, encoding="utf-8")
        toc.append((title, filename))

    info = metadata_markdown(metadata, epub)
    description = str(metadata.get("description") or "").strip()
    if description:
        info += f"# 作品简介\n\n{description}\n"
    (output / "0000_书籍信息.md").write_text(info, encoding="utf-8")

    toc_lines = [f"# {metadata.get('title') or epub.stem}目录", ""]
    toc_lines.extend(
        f"{index}. [{title}]({quote(filename)})"
        for index, (title, filename) in enumerate(toc, start=1)
    )
    (output / "目录.md").write_text("\n".join(toc_lines) + "\n", encoding="utf-8")

    created = list(output.glob("[0-9]*_*.md"))
    chapter_files = [path for path in created if not path.name.startswith("0000_")]
    if len(chapter_files) != len(chapters):
        raise ValueError(
            f"输出章节数不一致：EPUB {len(chapters)}，Markdown {len(chapter_files)}"
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="按 EPUB spine 顺序转换番茄小说：长篇分章 Markdown，短故事单个 Markdown。"
    )
    parser.add_argument("epub", type=Path, help="Tomato Novel Downloader 生成的 EPUB")
    parser.add_argument(
        "--type",
        required=True,
        choices=("novel", "story"),
        dest="content_type",
        help="novel=长篇并按章保存；story=短故事并合并为一个文件",
    )
    parser.add_argument("--output", type=Path, help="输出目录（novel）或 .md 文件（story）")
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="仅允许覆盖 story 的现有 Markdown 文件；不会覆盖非空 novel 目录",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    epub = args.epub.expanduser().resolve()
    if not epub.is_file():
        print(f"错误：EPUB 文件不存在：{epub}", file=sys.stderr)
        return 2
    output = (args.output or default_output(epub, args.content_type)).expanduser().resolve()

    try:
        metadata, chapters = epub_contents(epub)
        if args.content_type == "story":
            convert_story(epub, output, metadata, chapters, args.overwrite)
        else:
            convert_novel(epub, output, metadata, chapters)
    except (OSError, ValueError) as exc:
        print(f"错误：{exc}", file=sys.stderr)
        return 1

    print(f"类型：{'长篇小说' if args.content_type == 'novel' else '短故事'}")
    print(f"书名：{metadata.get('title') or epub.stem}")
    print(f"EPUB 章节数：{len(chapters)}")
    print(f"Markdown 输出：{output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
