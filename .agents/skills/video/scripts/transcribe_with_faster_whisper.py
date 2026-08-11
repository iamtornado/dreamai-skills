#!/usr/bin/env python3
"""Transcribe a local video with faster-whisper and emit WebVTT + JSON."""

from __future__ import annotations

import argparse
import ctypes
import importlib
import json
import os
import re
import sys
import time
from contextlib import redirect_stdout
from pathlib import Path
from typing import Any


SKILL_DIR = Path(__file__).resolve().parent.parent
DEFAULT_MODEL = "large-v3"
DEFAULT_CACHE_DIR = SKILL_DIR / ".cache" / "faster-whisper"
MODELSCOPE_REPOS = {
    "tiny": "Systran/faster-whisper-tiny",
    "base": "Systran/faster-whisper-base",
    "small": "Systran/faster-whisper-small",
    "medium": "Systran/faster-whisper-medium",
    "large-v2": "Systran/faster-whisper-large-v2",
    "large-v3": "Systran/faster-whisper-large-v3",
    "large-v3-turbo": "Systran/faster-whisper-large-v3-turbo",
    "turbo": "Systran/faster-whisper-large-v3-turbo",
}
CUDA_LIBRARY_HANDLES: list[ctypes.CDLL] = []


def log(message: str) -> None:
    print(message, file=sys.stderr, flush=True)


def preload_cuda_libraries() -> list[str]:
    """Load CUDA wheel libraries globally before CTranslate2 initializes CUDA."""
    if sys.platform != "linux":
        return []

    loaded: list[str] = []
    for module_name, library_name in (
        ("nvidia.cublas.lib", "libcublas.so.12"),
        ("nvidia.cudnn.lib", "libcudnn.so.9"),
    ):
        try:
            module = importlib.import_module(module_name)
            library = Path(module.__file__).resolve().parent / library_name
            handle = ctypes.CDLL(str(library), mode=os.RTLD_NOW | os.RTLD_GLOBAL)
        except (ImportError, OSError, TypeError) as error:
            package = module_name.removeprefix("nvidia.").removesuffix(".lib")
            raise RuntimeError(
                f"Unable to load {library_name} from nvidia-{package}-cu12; "
                "rerun scripts/install_paddleocr.sh"
            ) from error
        CUDA_LIBRARY_HANDLES.append(handle)
        loaded.append(str(library))
    log(f"[speech] Preloaded CUDA libraries: {', '.join(loaded)}")
    return loaded


def safe_name(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "-", value).strip("-.") or "whisper"


def is_ctranslate2_model(path: Path) -> bool:
    return (path / "config.json").is_file() and (path / "model.bin").is_file()


def resolve_model(model: str, source: str, cache_dir: Path) -> tuple[str, str]:
    """Return a faster-whisper model path/name and its provenance."""
    local = Path(model).expanduser()
    if local.is_dir():
        if not is_ctranslate2_model(local):
            raise RuntimeError(f"Not a CTranslate2 Whisper model directory: {local}")
        return str(local.resolve()), "local"

    repo = MODELSCOPE_REPOS.get(model)
    model_dir = cache_dir / f"modelscope-{safe_name(model)}"
    if is_ctranslate2_model(model_dir):
        return str(model_dir.resolve()), "modelscope-cache"

    if source in {"modelscope", "auto"} and repo:
        log(f"[speech] Downloading {repo} from ModelScope into {model_dir}")
        try:
            from modelscope.hub.snapshot_download import snapshot_download

            model_dir.mkdir(parents=True, exist_ok=True)
            # ModelScope progress uses stdout; reserve stdout for machine-readable JSON.
            with redirect_stdout(sys.stderr):
                resolved = Path(snapshot_download(repo, local_dir=str(model_dir), max_workers=8))
            if not is_ctranslate2_model(resolved):
                raise RuntimeError(f"Downloaded repository is not a CTranslate2 model: {resolved}")
            return str(resolved.resolve()), "modelscope"
        except Exception:
            if source == "modelscope":
                raise
            log("[speech] ModelScope download failed; falling back to faster-whisper/Hugging Face")

    if source == "modelscope":
        raise RuntimeError(f"No ModelScope CTranslate2 mapping is configured for model: {model}")
    cache_dir.mkdir(parents=True, exist_ok=True)
    return model, "huggingface"


def vtt_timestamp(seconds: float) -> str:
    milliseconds = max(0, round(seconds * 1000))
    hours, remainder = divmod(milliseconds, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    secs, millis = divmod(remainder, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}.{millis:03d}"


def compact_timestamp(seconds: float) -> str:
    total = max(0, round(seconds))
    hours, remainder = divmod(total, 3600)
    minutes, secs = divmod(remainder, 60)
    return f"{hours}:{minutes:02d}:{secs:02d}" if hours else f"{minutes}:{secs:02d}"


def model_matches(recorded: str, requested: str) -> bool:
    aliases = {requested, f"faster-whisper-{requested}"}
    if requested == "turbo":
        aliases.update({"large-v3-turbo", "faster-whisper-large-v3-turbo"})
    return recorded in aliases


def cache_matches(
    payload: dict[str, Any],
    *,
    model: str,
    language: str | None,
    hotwords: str | None,
    beam_size: int,
) -> bool:
    """Match text-affecting settings; execution tuning does not invalidate text."""
    recorded_language = payload.get("requestedLanguage", payload.get("language"))
    return (
        model_matches(str(payload.get("model", "")), model)
        and recorded_language == language
        and (payload.get("hotwords") or None) == (hotwords or None)
        and payload.get("beamSize") == beam_size
    )


def artifact_paths(video: Path, output_dir: Path, model: str) -> tuple[Path, Path]:
    primary_vtt = output_dir / f"{video.stem}.vtt"
    primary_json = output_dir / f"{video.stem}.transcript.json"
    if not primary_vtt.exists() and not primary_json.exists():
        return primary_vtt, primary_json
    try:
        payload = json.loads(primary_json.read_text(encoding="utf-8"))
        if model_matches(str(payload.get("model", "")), model):
            return primary_vtt, primary_json
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        pass
    suffix = safe_name(model)
    return output_dir / f"{video.stem}.{suffix}.vtt", output_dir / f"{video.stem}.{suffix}.transcript.json"


def payload_to_transcript(payload: dict[str, Any]) -> list[dict[str, Any]]:
    transcript: list[dict[str, Any]] = []
    for segment in payload.get("segments") or []:
        start = float(segment.get("start") or 0)
        end = float(segment.get("end") or start)
        transcript.append(
            {
                "time": compact_timestamp(start),
                "endTime": compact_timestamp(end),
                "startSeconds": round(start, 3),
                "endSeconds": round(end, 3),
                "text": str(segment.get("text") or "").strip(),
            }
        )
    return transcript


def write_vtt(path: Path, segments: list[dict[str, Any]]) -> None:
    lines = ["WEBVTT", ""]
    for index, segment in enumerate(segments, start=1):
        lines.extend(
            [
                str(index),
                f"{vtt_timestamp(float(segment['start']))} --> {vtt_timestamp(float(segment['end']))}",
                str(segment["text"]).strip(),
                "",
            ]
        )
    path.write_text("\n".join(lines), encoding="utf-8")


def transcribe_video(
    video: Path,
    output_dir: Path,
    *,
    model: str = DEFAULT_MODEL,
    model_source: str = "modelscope",
    language: str | None = None,
    device: str = "cuda",
    device_index: int = 0,
    compute_type: str = "float16",
    batch_size: int = 8,
    beam_size: int = 5,
    hotwords: str | None = None,
    force_refresh: bool = False,
) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    vtt_path, json_path = artifact_paths(video, output_dir, model)
    if not force_refresh and vtt_path.is_file() and json_path.is_file():
        try:
            cached = json.loads(json_path.read_text(encoding="utf-8"))
            if cache_matches(
                cached,
                model=model,
                language=language,
                hotwords=hotwords,
                beam_size=beam_size,
            ):
                log(f"[speech] Reusing cached {model} transcript at {json_path}")
                return {
                    "transcript": payload_to_transcript(cached),
                    "payload": cached,
                    "vttPath": str(vtt_path.resolve()),
                    "jsonPath": str(json_path.resolve()),
                    "cached": True,
                }
            log(f"[speech] Cached {model} transcript settings differ; regenerating")
        except (json.JSONDecodeError, OSError):
            pass

    if device == "cuda":
        preload_cuda_libraries()
    from faster_whisper import BatchedInferencePipeline, WhisperModel

    cache_dir = DEFAULT_CACHE_DIR
    resolved_model, model_provenance = resolve_model(model, model_source, cache_dir)
    log(
        f"[speech] Loading faster-whisper {model}; device={device}:{device_index}; "
        f"compute_type={compute_type}; batch_size={batch_size}"
    )
    whisper = WhisperModel(
        resolved_model,
        device=device,
        device_index=device_index,
        compute_type=compute_type,
        download_root=str(cache_dir / "huggingface"),
    )
    pipeline = BatchedInferencePipeline(model=whisper)
    started = time.monotonic()
    segment_iterator, info = pipeline.transcribe(
        str(video),
        language=language,
        beam_size=beam_size,
        vad_filter=True,
        batch_size=batch_size,
        hotwords=hotwords or None,
        log_progress=True,
    )
    segments = [
        {
            "start": round(float(segment.start), 3),
            "end": round(float(segment.end), 3),
            "text": segment.text.strip(),
        }
        for segment in segment_iterator
        if segment.text.strip()
    ]
    elapsed = round(time.monotonic() - started, 3)
    payload = {
        "model": model,
        "modelProvenance": model_provenance,
        "device": device,
        "deviceIndex": device_index,
        "computeType": compute_type,
        "batchSize": batch_size,
        "beamSize": beam_size,
        "vadFilter": True,
        "hotwords": hotwords or None,
        "requestedLanguage": language,
        "language": info.language,
        "languageProbability": round(float(info.language_probability), 6),
        "duration": round(float(info.duration), 6),
        "durationAfterVad": round(float(info.duration_after_vad), 6),
        "elapsedSeconds": elapsed,
        "segments": segments,
    }
    write_vtt(vtt_path, segments)
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    log(f"[speech] Wrote {len(segments)} segments to {vtt_path} in {elapsed:.2f}s")
    return {
        "transcript": payload_to_transcript(payload),
        "payload": payload,
        "vttPath": str(vtt_path.resolve()),
        "jsonPath": str(json_path.resolve()),
        "cached": False,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("video", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--model-source", choices=("modelscope", "huggingface", "auto"), default="modelscope")
    parser.add_argument("--language", help="Forced language; omitted means automatic detection")
    parser.add_argument("--device", choices=("cuda", "cpu"), default="cuda")
    parser.add_argument("--device-index", type=int, default=0)
    parser.add_argument("--compute-type", default="float16")
    parser.add_argument("--batch-size", type=int, default=8)
    parser.add_argument("--beam-size", type=int, default=5)
    parser.add_argument("--hotwords")
    parser.add_argument("--force-refresh", action="store_true")
    args = parser.parse_args()
    if not args.video.is_file():
        parser.error(f"video does not exist: {args.video}")
    if args.batch_size < 1:
        parser.error("--batch-size must be positive")
    if args.beam_size < 1:
        parser.error("--beam-size must be positive")
    return args


def main() -> int:
    args = parse_args()
    result = transcribe_video(
        args.video.resolve(),
        args.out.resolve(),
        model=args.model,
        model_source=args.model_source,
        language=args.language,
        device=args.device,
        device_index=args.device_index,
        compute_type=args.compute_type,
        batch_size=args.batch_size,
        beam_size=args.beam_size,
        hotwords=args.hotwords,
        force_refresh=args.force_refresh,
    )
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
