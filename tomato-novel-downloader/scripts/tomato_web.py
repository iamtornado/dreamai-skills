#!/usr/bin/env python3
"""Cross-platform controller for Tomato Novel Downloader's Web API."""

from __future__ import annotations

import argparse
import json
import os
import platform
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from resolve_book_id import resolve


PROXY_VARIABLES = (
    "HTTP_PROXY",
    "HTTPS_PROXY",
    "ALL_PROXY",
    "http_proxy",
    "https_proxy",
    "all_proxy",
)
TERMINAL_STATES = {"done", "failed", "canceled"}


def print_json(value: object) -> None:
    print(json.dumps(value, ensure_ascii=False, indent=2))


def server_environment(address: str) -> dict[str, str]:
    """Return an isolated child environment that bypasses proxies."""
    environment = os.environ.copy()
    for name in PROXY_VARIABLES:
        environment.pop(name, None)
    environment["NO_PROXY"] = "127.0.0.1,localhost"
    environment["no_proxy"] = "127.0.0.1,localhost"
    environment["TOMATO_WEB_ADDR"] = address
    return environment


def resolve_binary(path: Path) -> Path:
    candidate = path.expanduser().resolve()
    if candidate.is_file():
        return candidate
    if platform.system().lower() == "windows" and candidate.suffix.lower() != ".exe":
        windows_candidate = Path(str(candidate) + ".exe")
        if windows_candidate.is_file():
            return windows_candidate
    raise ValueError(f"下载器可执行文件不存在：{candidate}")


def validate_bind(address: str, password: str | None) -> None:
    host = address.rsplit(":", 1)[0].strip("[]").lower()
    if host not in {"127.0.0.1", "localhost", "::1"} and not password:
        raise ValueError("监听非本机地址时必须设置 --password")


class ApiClient:
    def __init__(self, base_url: str, password: str | None, timeout: float) -> None:
        self.base_url = base_url.rstrip("/")
        self.password = password
        self.timeout = timeout
        self.opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))

    def request(self, method: str, path: str, payload: object | None = None):
        headers = {"accept": "application/json"}
        body = None
        if self.password:
            headers["x-tomato-password"] = self.password
        if payload is not None:
            headers["content-type"] = "application/json"
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        request = urllib.request.Request(
            self.base_url + path,
            data=body,
            headers=headers,
            method=method,
        )
        try:
            with self.opener.open(request, timeout=self.timeout) as response:
                raw = response.read()
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace").strip()
            raise RuntimeError(f"HTTP {exc.code} {method} {path}: {detail}") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"无法连接 {self.base_url}：{exc.reason}") from exc
        if not raw:
            return None
        try:
            return json.loads(raw)
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"服务器返回的不是 JSON：{raw[:200]!r}") from exc


def make_client(args: argparse.Namespace) -> ApiClient:
    return ApiClient(args.base_url, args.password, args.request_timeout)


def wait_until_ready(client: ApiClient, timeout: float, interval: float):
    deadline = time.monotonic() + timeout
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        try:
            status = client.request("GET", "/api/status")
            prewarm_error = status.get("prewarm_error")
            if prewarm_error:
                raise RuntimeError(f"IID 预热失败：{prewarm_error}")
            if not status.get("prewarm_in_progress"):
                return status
        except RuntimeError as exc:
            if "IID 预热失败" in str(exc):
                raise
            last_error = exc
        time.sleep(interval)
    detail = f"；最后错误：{last_error}" if last_error else ""
    raise RuntimeError(f"等待服务就绪超时（{timeout:g} 秒）{detail}")


def normalize_book_input(value: str, allow_share: bool = False) -> str:
    try:
        return resolve(value, timeout=20.0, use_env_proxy=False)
    except ValueError:
        parsed = urllib.parse.urlparse(value.strip())
        if (
            allow_share
            and parsed.scheme in {"http", "https"}
            and parsed.hostname in {"fanqienovel.com", "www.fanqienovel.com"}
            and parsed.path.startswith("/t/")
        ):
            return value.strip()
        raise


def command_serve(args: argparse.Namespace) -> int:
    binary = resolve_binary(args.binary)
    data_dir = args.data_dir.expanduser().resolve()
    data_dir.mkdir(parents=True, exist_ok=True)
    validate_bind(args.address, args.password)
    command = [str(binary), "--server", "--data-dir", str(data_dir)]
    if args.password:
        command.extend(["--password", args.password])
    print(f"启动：{binary}")
    print(f"数据目录：{data_dir}")
    print(f"监听地址：http://{args.address}")
    try:
        return subprocess.run(
            command,
            env=server_environment(args.address),
            check=False,
        ).returncode
    except KeyboardInterrupt:
        return 130


def command_status(args: argparse.Namespace) -> int:
    print_json(make_client(args).request("GET", "/api/status"))
    return 0


def command_wait_ready(args: argparse.Namespace) -> int:
    status = wait_until_ready(make_client(args), args.timeout, args.interval)
    print_json(status)
    return 0


def command_configure(args: argparse.Namespace) -> int:
    client = make_client(args)
    config = client.request("GET", "/api/config/full")
    if not isinstance(config, dict):
        raise RuntimeError("/api/config/full 未返回配置对象")

    if args.output_format == "bulk-txt":
        config["novel_format"] = "txt"
        config["bulk_files"] = True
    else:
        config["novel_format"] = args.output_format
        config["bulk_files"] = False
    config["ask_format_after_download"] = False
    config["auto_clear_dump"] = False
    config["auto_open_downloaded_files"] = False

    save_path = args.save_path.expanduser().resolve()
    save_path.mkdir(parents=True, exist_ok=True)
    config["save_path"] = str(save_path)
    result = client.request("POST", "/api/config/full", config)
    print_json(
        {
            "ok": bool(result and result.get("ok")),
            "novel_format": config["novel_format"],
            "bulk_files": config["bulk_files"],
            "save_path": config["save_path"],
        }
    )
    return 0


def command_preview(args: argparse.Namespace) -> int:
    book_id = normalize_book_input(args.input)
    result = make_client(args).request(
        "GET", f"/api/preview/{urllib.parse.quote(book_id, safe='')}"
    )
    print_json(result)
    return 0


def command_jobs(args: argparse.Namespace) -> int:
    query = "?all=true" if args.all else ""
    print_json(make_client(args).request("GET", "/api/jobs" + query))
    return 0


def wait_for_job(
    client: ApiClient,
    job_id: int,
    timeout: float,
    interval: float,
):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        result = client.request("GET", f"/api/jobs?id={job_id}")
        items = result.get("items", []) if isinstance(result, dict) else []
        if not items:
            raise RuntimeError(f"任务不存在：{job_id}")
        job = items[0]
        if job.get("book_name_options"):
            raise RuntimeError("任务正在等待书名选择；请在 Web UI 中选择后重试等待")
        if job.get("format_options"):
            raise RuntimeError("任务正在等待格式选择；先运行 configure 禁用下载后询问")
        state = str(job.get("state", "")).lower()
        if state in TERMINAL_STATES:
            return job
        time.sleep(interval)
    raise RuntimeError(f"等待任务 {job_id} 超时（{timeout:g} 秒）")


def validate_finished_job(job: dict) -> None:
    state = str(job.get("state", "")).lower()
    if state != "done":
        raise RuntimeError(f"下载任务未成功：{state}；{job.get('message') or ''}")
    progress = job.get("progress") or {}
    saved = progress.get("saved_chapters")
    total = progress.get("chapter_total")
    if isinstance(saved, int) and isinstance(total, int) and total > 0 and saved < total:
        raise RuntimeError(f"下载任务不完整：{saved}/{total} 章")


def command_download(args: argparse.Namespace) -> int:
    client = make_client(args)
    wait_until_ready(client, args.ready_timeout, args.interval)
    book_input = normalize_book_input(args.input, allow_share=True)
    payload: dict[str, object] = {"book_id": book_input}
    if args.range_start is not None or args.range_end is not None:
        if args.range_start is None or args.range_end is None:
            raise ValueError("--range-start 和 --range-end 必须同时提供")
        payload["range_start"] = args.range_start
        payload["range_end"] = args.range_end
    created = client.request("POST", "/api/jobs", payload)
    if args.no_wait:
        print_json(created)
        return 0
    job = wait_for_job(client, int(created["id"]), args.timeout, args.interval)
    print_json(job)
    validate_finished_job(job)
    return 0


def add_api_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--base-url", default="http://127.0.0.1:18423")
    parser.add_argument("--password", help="Web UI 密码（如已启用）")
    parser.add_argument("--request-timeout", type=float, default=30.0)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Linux/Windows 通用的番茄小说下载器 Web API 控制器。"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    serve = subparsers.add_parser("serve", help="以前台方式启动 Web UI 服务")
    serve.add_argument("--binary", required=True, type=Path)
    serve.add_argument("--data-dir", required=True, type=Path)
    serve.add_argument("--address", default="127.0.0.1:18423")
    serve.add_argument("--password")
    serve.set_defaults(func=command_serve)

    status = subparsers.add_parser("status", help="读取服务状态")
    add_api_options(status)
    status.set_defaults(func=command_status)

    ready = subparsers.add_parser("wait-ready", help="等待服务和 IID 预热就绪")
    add_api_options(ready)
    ready.add_argument("--timeout", type=float, default=120.0)
    ready.add_argument("--interval", type=float, default=2.0)
    ready.set_defaults(func=command_wait_ready)

    configure = subparsers.add_parser("configure", help="配置输出格式和保存目录")
    add_api_options(configure)
    configure.add_argument(
        "--format",
        dest="output_format",
        required=True,
        choices=("epub", "txt", "pdf", "bulk-txt"),
    )
    configure.add_argument("--save-path", required=True, type=Path)
    configure.set_defaults(func=command_configure)

    preview = subparsers.add_parser("preview", help="预览 Book ID 或番茄链接")
    add_api_options(preview)
    preview.add_argument("input")
    preview.set_defaults(func=command_preview)

    jobs = subparsers.add_parser("jobs", help="列出下载任务")
    add_api_options(jobs)
    jobs.add_argument("--all", action="store_true")
    jobs.set_defaults(func=command_jobs)

    download = subparsers.add_parser("download", help="创建并等待下载任务")
    add_api_options(download)
    download.add_argument("input")
    download.add_argument("--range-start", type=int)
    download.add_argument("--range-end", type=int)
    download.add_argument("--no-wait", action="store_true")
    download.add_argument("--ready-timeout", type=float, default=120.0)
    download.add_argument("--timeout", type=float, default=14400.0)
    download.add_argument("--interval", type=float, default=2.0)
    download.set_defaults(func=command_download)

    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        return args.func(args)
    except (OSError, RuntimeError, ValueError, KeyError) as exc:
        print(f"错误：{exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
