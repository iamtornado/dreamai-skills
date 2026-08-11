#!/usr/bin/env bash
set -euo pipefail

skill_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
venv="$skill_dir/.venv"

command -v uv >/dev/null || { echo "uv is required" >&2; exit 1; }
uv venv "$venv" --python /usr/bin/python3.12
uv pip install --python "$venv/bin/python" \
  paddlepaddle-gpu==3.3.0 \
  --index-url https://www.paddlepaddle.org.cn/packages/stable/cu126/
uv pip install --python "$venv/bin/python" \
  paddleocr==3.7.0 \
  faster-whisper==1.2.1 \
  modelscope==1.39.1 \
  socksio==1.0.0 \
  nvidia-cublas-cu12==12.6.4.1 \
  nvidia-cudnn-cu12==9.5.1.17
"$venv/bin/python" -c 'from importlib.metadata import version; import faster_whisper; import modelscope; import paddle; import paddleocr; import socksio; fw = version("faster-whisper"); ms = version("modelscope"); si = version("socksio"); print(f"Paddle={paddle.__version__} PaddleOCR={paddleocr.__version__} CUDA={paddle.is_compiled_with_cuda()} GPUs={paddle.device.cuda.device_count()} faster-whisper={fw} ModelScope={ms} socksio={si}")'
