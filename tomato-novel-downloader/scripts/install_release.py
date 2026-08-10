#!/usr/bin/env python3
"""Install and SHA-256 verify the latest Tomato-Novel-Downloader release."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import stat
import sys
import tempfile
import urllib.request
from pathlib import Path


LATEST_API = "https://api.github.com/repos/zhongbai2333/Tomato-Novel-Downloader/releases/latest"


def asset_prefix() -> str:
    system = platform.system().lower()
    machine = platform.machine().lower()
    arm64 = machine in {"arm64", "aarch64"}
    amd64 = machine in {"x86_64", "amd64"}
    if system == "linux" and amd64:
        return "TomatoNovelDownloader-Linux_amd64-v"
    if system == "linux" and arm64:
        return "TomatoNovelDownloader-Linux_arm64-v"
    if system == "darwin" and amd64:
        return "TomatoNovelDownloader-macOS_amd64-v"
    if system == "darwin" and arm64:
        return "TomatoNovelDownloader-macOS_arm64-v"
    if system == "windows" and amd64:
        return "TomatoNovelDownloader-Win64-v"
    if system == "windows" and arm64:
        return "TomatoNovelDownloader-WinArm64-v"
    raise RuntimeError(f"unsupported platform: {system}/{machine}")


def normalize_output_path(output: Path) -> Path:
    """Append .exe on Windows so the installed binary is directly runnable."""
    if platform.system().lower() == "windows" and output.suffix.lower() != ".exe":
        return Path(str(output) + ".exe")
    return output


def get_json(url: str) -> dict:
    request = urllib.request.Request(url, headers={"User-Agent": "Codex tomato skill"})
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path, help="absolute binary path")
    args = parser.parse_args()

    output = normalize_output_path(args.output.expanduser())
    if not output.is_absolute():
        print("error: --output must be absolute", file=sys.stderr)
        return 2

    try:
        release = get_json(LATEST_API)
        prefix = asset_prefix()
        asset = next(item for item in release["assets"] if item["name"].startswith(prefix))
        expected = str(asset.get("digest", ""))
        if not expected.startswith("sha256:"):
            raise RuntimeError("release asset has no SHA-256 digest")
        expected_hash = expected.split(":", 1)[1].lower()

        output.parent.mkdir(parents=True, exist_ok=True)
        hasher = hashlib.sha256()
        request = urllib.request.Request(
            asset["browser_download_url"], headers={"User-Agent": "Codex tomato skill"}
        )
        with tempfile.NamedTemporaryFile(dir=output.parent, delete=False) as temp:
            temp_path = Path(temp.name)
            with urllib.request.urlopen(request, timeout=120) as response:
                while chunk := response.read(1024 * 1024):
                    temp.write(chunk)
                    hasher.update(chunk)

        actual_hash = hasher.hexdigest()
        if actual_hash != expected_hash:
            temp_path.unlink(missing_ok=True)
            raise RuntimeError(f"digest mismatch: {actual_hash} != {expected_hash}")

        os.replace(temp_path, output)
        if platform.system().lower() != "windows":
            output.chmod(output.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
        print(
            json.dumps(
                {
                    "version": release["tag_name"],
                    "asset": asset["name"],
                    "output": str(output),
                    "sha256": actual_hash,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
