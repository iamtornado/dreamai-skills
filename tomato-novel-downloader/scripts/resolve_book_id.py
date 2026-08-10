#!/usr/bin/env python3
"""Resolve a Fanqie Book ID, including reader item URLs."""

from __future__ import annotations

import argparse
import re
import sys
import urllib.parse
import urllib.request


PAGE_RE = re.compile(r"/page/(\d+)")
READER_RE = re.compile(r"/reader/(\d+)")
QUERY_RE = re.compile(r"(?:^|[?&#])(?:book_id|bookId)=(\d+)", re.I)
EMBEDDED_BOOK_RE = re.compile(r'"(?:bookId|book_id)"\s*:\s*"?(\d+)')
ALLOWED_HOSTS = {"fanqienovel.com", "www.fanqienovel.com"}


def fetch_reader_book_id(url: str, timeout: float, use_env_proxy: bool) -> str:
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme not in {"http", "https"} or parsed.hostname not in ALLOWED_HOSTS:
        raise ValueError("reader URL must use fanqienovel.com")

    handlers = [] if use_env_proxy else [urllib.request.ProxyHandler({})]
    opener = urllib.request.build_opener(*handlers)
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 Chrome/120 Safari/537.36"
            )
        },
    )
    with opener.open(request, timeout=timeout) as response:
        html = response.read().decode("utf-8", errors="replace")

    match = EMBEDDED_BOOK_RE.search(html)
    if not match:
        raise ValueError("reader page did not expose an embedded bookId")
    return match.group(1)


def resolve(value: str, timeout: float, use_env_proxy: bool) -> str:
    value = value.strip()
    if value.isdigit():
        return value

    query_match = QUERY_RE.search(value)
    if query_match:
        return query_match.group(1)

    page_match = PAGE_RE.search(value)
    if page_match:
        return page_match.group(1)

    if READER_RE.search(value):
        return fetch_reader_book_id(value, timeout, use_env_proxy)

    raise ValueError("unsupported input: expected Book ID, /page/ URL, or /reader/ URL")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", help="Book ID or Fanqie URL")
    parser.add_argument("--timeout", type=float, default=20.0)
    parser.add_argument(
        "--use-env-proxy",
        action="store_true",
        help="honor HTTP(S)_PROXY for reader-page resolution",
    )
    args = parser.parse_args()

    try:
        print(resolve(args.input, args.timeout, args.use_env_proxy))
        return 0
    except Exception as exc:  # concise CLI error boundary
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
