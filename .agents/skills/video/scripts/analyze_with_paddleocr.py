#!/usr/bin/env python3
"""Analyze a video with mcp-video-analyzer for speech and PaddleOCR for visuals."""

from __future__ import annotations

import argparse
import base64
import hashlib
import html
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.parse
import urllib.request
from contextlib import redirect_stdout
from pathlib import Path
from statistics import fmean
from typing import Any


SKILL_DIR = Path(__file__).resolve().parent.parent


def log(message: str) -> None:
    print(message, file=sys.stderr, flush=True)


def run(command: list[str], *, timeout: int | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=timeout,
    )


def format_time(seconds: float) -> str:
    total = max(0, round(seconds))
    hours, remainder = divmod(total, 3600)
    minutes, secs = divmod(remainder, 60)
    return f"{hours}:{minutes:02d}:{secs:02d}" if hours else f"{minutes}:{secs:02d}"


def parse_time(value: str) -> int:
    parts = [int(part) for part in value.split(":")]
    if len(parts) == 3:
        return parts[0] * 3600 + parts[1] * 60 + parts[2]
    if len(parts) == 2:
        return parts[0] * 60 + parts[1]
    return 0


def fanqie_play_url(source: str) -> str:
    request = urllib.request.Request(source, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(request, timeout=30) as response:
        page = html.unescape(response.read().decode("utf-8", errors="replace"))
    token_match = re.search(r'data-token=\\?"([^"\\]+)', page)
    if not token_match:
        raise RuntimeError("Fanqie page does not contain an anonymous video token")
    token = token_match.group(1)
    decoded = base64.b64decode(token + "===").decode("utf-8")
    query = json.loads(decoded)["GetPlayInfoToken"]
    with urllib.request.urlopen(f"https://vod.bytedanceapi.com/?{query}", timeout=30) as response:
        payload = json.load(response)
    choices = payload["Result"]["Data"]["PlayInfoList"]
    if not choices:
        raise RuntimeError("Fanqie VOD response contains no playable rendition")
    best = max(
        choices,
        key=lambda item: (
            int(item.get("Width") or 0) * int(item.get("Height") or 0),
            int(item.get("Bitrate") or 0),
        ),
    )
    return str(best["MainPlayUrl"])


def resolve_source(source: str, output_dir: Path) -> tuple[Path, bool]:
    if source.startswith("file://"):
        path = Path(urllib.parse.unquote(urllib.parse.urlparse(source).path)).resolve()
        if not path.is_file():
            raise FileNotFoundError(path)
        return path, False
    local = Path(source).expanduser()
    if local.is_file():
        return local.resolve(), False
    parsed = urllib.parse.urlparse(source)
    if parsed.scheme not in {"http", "https"}:
        raise FileNotFoundError(f"Video source does not exist: {source}")
    if not shutil.which("yt-dlp"):
        raise RuntimeError("yt-dlp is required to download web video sources")
    host = (parsed.hostname or "").lower()
    is_fanqie = host == "fanqienovel.com" or host.endswith(".fanqienovel.com")
    downloadable = fanqie_play_url(source) if is_fanqie else source
    output_template = str(output_dir / "source.%(ext)s")
    log("[download] Resolving and downloading the video with yt-dlp")
    command = [
        "yt-dlp",
        "--no-playlist",
        "--merge-output-format",
        "mp4",
        "--output",
        output_template,
        "--print",
        "after_move:filepath",
    ]
    if os.environ.get("YTDLP_COOKIES"):
        command.extend(["--cookies", os.environ["YTDLP_COOKIES"]])
    elif os.environ.get("YTDLP_COOKIES_FROM_BROWSER"):
        command.extend(["--cookies-from-browser", os.environ["YTDLP_COOKIES_FROM_BROWSER"]])
    completed = run([*command, downloadable])
    candidates = [Path(line.strip()) for line in completed.stdout.splitlines() if line.strip()]
    if not candidates or not candidates[-1].is_file():
        candidates = sorted(output_dir.glob("source.*"), key=lambda item: item.stat().st_mtime)
    if not candidates:
        raise RuntimeError(f"yt-dlp did not produce a video file: {completed.stderr.strip()}")
    return candidates[-1].resolve(), True


def probe_video(video: Path) -> dict[str, Any]:
    completed = run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_format",
            "-show_streams",
            "-of",
            "json",
            str(video),
        ],
        timeout=60,
    )
    raw = json.loads(completed.stdout)
    streams = raw.get("streams", [])
    video_stream = next((item for item in streams if item.get("codec_type") == "video"), {})
    audio_stream = next((item for item in streams if item.get("codec_type") == "audio"), {})
    duration = float(raw.get("format", {}).get("duration") or video_stream.get("duration") or 0)
    frame_rate = str(video_stream.get("avg_frame_rate") or video_stream.get("r_frame_rate") or "0/1")
    numerator, denominator = (frame_rate.split("/") + ["1"])[:2]
    fps = float(numerator) / float(denominator or 1)
    return {
        "platform": "local",
        "title": video.name,
        "duration": round(duration, 3),
        "durationFormatted": format_time(duration),
        "url": str(video),
        "width": video_stream.get("width"),
        "height": video_stream.get("height"),
        "fps": round(fps, 3),
        "videoCodec": video_stream.get("codec_name"),
        "audioCodec": audio_stream.get("codec_name"),
        "hasAudio": bool(audio_stream),
        "fileSizeBytes": video.stat().st_size,
    }


def analyzer_brief(video: Path, args: argparse.Namespace) -> dict[str, Any]:
    command = [
        "npx",
        "-y",
        args.analyzer_package,
        "analyze",
        str(video),
        "--detail",
        "brief",
        "--fields",
        "metadata,transcript",
    ]
    if args.language:
        command.extend(["--language", args.language])
    if args.model:
        command.extend(["--model", args.model])
    if args.force_refresh:
        command.append("--force-refresh")
    log("[speech] Running mcp-video-analyzer in brief mode (Tesseract is skipped)")
    try:
        completed = run(command, timeout=args.analyzer_timeout)
        return json.loads(completed.stdout)
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, json.JSONDecodeError) as error:
        detail = getattr(error, "stderr", None) or str(error)
        log(f"[speech] Analyzer degraded to metadata-only output: {detail.strip()}")
        return {"metadata": probe_video(video), "transcript": [], "warnings": [str(detail).strip()]}


def sample_times(duration: float, count: int) -> list[float]:
    if duration <= 0 or count < 1:
        return []
    return [duration * (index + 0.5) / count for index in range(count)]


def extract_frames(video: Path, output_dir: Path, duration: float, count: int, max_width: int) -> list[dict[str, Any]]:
    from PIL import Image

    frame_dir = output_dir / "frames"
    original_dir = frame_dir / "original"
    original_dir.mkdir(parents=True, exist_ok=True)
    frames: list[dict[str, Any]] = []
    for index, seconds in enumerate(sample_times(duration, count), start=1):
        original = original_dir / f"frame_{index:03d}.jpg"
        emitted = frame_dir / f"frame_{index:03d}.jpg"
        run(
            [
                "ffmpeg",
                "-hide_banner",
                "-loglevel",
                "error",
                "-ss",
                f"{seconds:.3f}",
                "-i",
                str(video),
                "-frames:v",
                "1",
                "-q:v",
                "2",
                "-y",
                str(original),
            ],
            timeout=60,
        )
        with Image.open(original) as image:
            if max_width > 0 and image.width > max_width:
                resized = image.copy()
                resized.thumbnail((max_width, 100_000), Image.Resampling.LANCZOS)
                resized.save(emitted, "JPEG", quality=88, optimize=True)
            else:
                image.save(emitted, "JPEG", quality=90, optimize=True)
        frames.append(
            {
                "time": format_time(seconds),
                "seconds": round(seconds, 3),
                "filePath": str(emitted.resolve()),
                "originalFilePath": str(original.resolve()),
                "mimeType": "image/jpeg",
            }
        )
        log(f"[frames] Extracted {index}/{count} at {format_time(seconds)}")
    return frames


def result_payload(result: Any) -> dict[str, Any]:
    payload = getattr(result, "json", None)
    if callable(payload):
        payload = payload()
    if payload is None and hasattr(result, "to_dict"):
        payload = result.to_dict()
    if isinstance(payload, str):
        payload = json.loads(payload)
    if not isinstance(payload, dict):
        try:
            payload = dict(result)
        except Exception as error:  # pragma: no cover - defensive API compatibility
            raise RuntimeError(f"Unsupported PaddleOCR result type: {type(result)!r}") from error
    nested = payload.get("res")
    return nested if isinstance(nested, dict) else payload


def to_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if hasattr(value, "tolist"):
        return value.tolist()
    return list(value)


def paddle_ocr(frames: list[dict[str, Any]], args: argparse.Namespace) -> list[dict[str, Any]]:
    # PaddleX and its model downloaders write progress messages to stdout.  Keep
    # stdout reserved for this wrapper's machine-readable JSON contract.
    with redirect_stdout(sys.stderr):
        return _paddle_ocr(frames, args)


def _paddle_ocr(frames: list[dict[str, Any]], args: argparse.Namespace) -> list[dict[str, Any]]:
    # BOS is Paddle's own model host and avoids interactive third-party progress
    # output. Users can still override either variable before launching.
    os.environ.setdefault("PADDLE_PDX_CACHE_HOME", str(SKILL_DIR / ".cache" / "paddlex"))
    os.environ.setdefault("PADDLE_PDX_MODEL_SOURCE", "bos")
    os.environ.setdefault("PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK", "True")
    import paddle
    from paddleocr import PaddleOCR

    if args.device.startswith("gpu") and not paddle.is_compiled_with_cuda():
        raise RuntimeError("GPU OCR requested, but PaddlePaddle is not compiled with CUDA")
    log(
        f"[ocr] Paddle {paddle.__version__}; device={args.device}; "
        f"CUDA={paddle.is_compiled_with_cuda()}; GPUs={paddle.device.cuda.device_count()}"
    )
    ocr = PaddleOCR(
        lang=args.ocr_language,
        device=args.device,
        use_doc_orientation_classify=False,
        use_doc_unwarping=False,
        use_textline_orientation=False,
        engine="paddle",
    )
    output: list[dict[str, Any]] = []
    for index, frame in enumerate(frames, start=1):
        results = ocr.predict(frame["originalFilePath"])
        accepted: list[dict[str, Any]] = []
        for result in results:
            payload = result_payload(result)
            texts = to_list(payload.get("rec_texts"))
            scores = to_list(payload.get("rec_scores"))
            box_values = payload.get("rec_boxes")
            if box_values is None:
                box_values = payload.get("rec_polys")
            boxes = to_list(box_values)
            for line_index, text in enumerate(texts):
                score = float(scores[line_index]) if line_index < len(scores) else 0.0
                if str(text).strip() and score >= args.min_confidence:
                    accepted.append(
                        {
                            "text": str(text).strip(),
                            "confidence": round(score, 4),
                            "box": boxes[line_index] if line_index < len(boxes) else None,
                        }
                    )
        if accepted:
            output.append(
                {
                    "time": frame["time"],
                    "text": "\n".join(line["text"] for line in accepted),
                    "confidence": round(fmean(line["confidence"] for line in accepted) * 100),
                    "engine": "PaddleOCR",
                    "device": args.device,
                    "lines": accepted,
                }
            )
        log(f"[ocr] Processed {index}/{len(frames)}; accepted {len(accepted)} line(s)")
    return output


def closest(entries: list[dict[str, Any]], seconds: int, tolerance: int = 2) -> dict[str, Any] | None:
    candidates = [entry for entry in entries if abs(int(entry["seconds"]) - seconds) <= tolerance]
    return min(candidates, key=lambda entry: abs(int(entry["seconds"]) - seconds), default=None)


def build_timeline(
    transcript: list[dict[str, Any]], frames: list[dict[str, Any]], ocr_results: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for item in transcript:
        entry = {"time": item.get("time", "0:00"), "seconds": parse_time(item.get("time", "0:00")), "transcript": item.get("text", "")}
        if item.get("speaker") is not None:
            entry["speaker"] = item["speaker"]
        entries.append(entry)
    for index, frame in enumerate(frames):
        seconds = parse_time(frame["time"])
        entry = closest(entries, seconds)
        if entry is None:
            entry = {"time": frame["time"], "seconds": seconds}
            entries.append(entry)
        entry["frameIndex"] = index
    for item in ocr_results:
        seconds = parse_time(item["time"])
        entry = closest(entries, seconds)
        if entry is None:
            entry = {"time": item["time"], "seconds": seconds}
            entries.append(entry)
        entry["ocrText"] = item["text"]
    return sorted(entries, key=lambda entry: int(entry["seconds"]))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", help="Local video, file:// URI, supported URL, or Fanqie article URL")
    parser.add_argument("--out", type=Path, help="Persistent output directory")
    parser.add_argument("--max-frames", type=int, default=12)
    parser.add_argument("--max-width", type=int, default=960, help="Emitted frame width; 0 keeps original resolution")
    parser.add_argument("--device", default="gpu:0", help="Paddle device, e.g. gpu:0 or cpu")
    parser.add_argument("--ocr-language", default="ch", help="PaddleOCR language/model selector")
    parser.add_argument("--min-confidence", type=float, default=0.45)
    parser.add_argument("--language", help="Forced Whisper language passed to mcp-video-analyzer")
    parser.add_argument("--model", help="Whisper model passed to mcp-video-analyzer")
    parser.add_argument("--force-refresh", action="store_true")
    parser.add_argument("--analyzer-package", default="mcp-video-analyzer@0.8.0")
    parser.add_argument("--analyzer-timeout", type=int, default=900)
    args = parser.parse_args()
    if not 1 <= args.max_frames <= 60:
        parser.error("--max-frames must be between 1 and 60")
    if not 0 <= args.min_confidence <= 1:
        parser.error("--min-confidence must be between 0 and 1")
    return args


def main() -> int:
    args = parse_args()
    digest = hashlib.sha256(args.source.encode()).hexdigest()[:12]
    output_dir = (args.out or Path(tempfile.gettempdir()) / "video-paddleocr" / digest).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    video, downloaded = resolve_source(args.source, output_dir)
    analysis = analyzer_brief(video, args)
    metadata = {**probe_video(video), **(analysis.get("metadata") or {})}
    duration = float(metadata.get("duration") or 0)
    frames = extract_frames(video, output_dir, duration, args.max_frames, args.max_width)
    ocr_results = paddle_ocr(frames, args)
    transcript = analysis.get("transcript") or []
    warnings = list(analysis.get("warnings") or [])
    warnings.append("Visual OCR generated by PaddleOCR; mcp-video-analyzer Tesseract OCR was skipped.")
    result = {
        "metadata": {**metadata, "ocrEngine": "PaddleOCR", "ocrDevice": args.device},
        "transcript": transcript,
        "frames": frames,
        "frameCount": len(frames),
        "ocrResults": ocr_results,
        "timeline": build_timeline(transcript, frames, ocr_results),
        "warnings": warnings,
        "artifacts": {"outputDir": str(output_dir), "video": str(video), "downloaded": downloaded},
    }
    analysis_path = output_dir / "analysis.json"
    analysis_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    log(f"[done] Wrote {analysis_path}")
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
