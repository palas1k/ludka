"""Metrics for evals."""

import os
from pathlib import Path

metrics = []

PROMPTS_DIR = Path(__file__).parent / "prompts"

for file_path in PROMPTS_DIR.glob("*.md"):
    metrics.append({"name": file_path.stem, "prompt": file_path.read_text()})
