"""Shared context passed to per-option producers (data-model.md, R4)."""

from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class RunContext:
    workdir: Path
    input_laz: Path
    resolution_m: float
    # Prerequisite option id -> local path to its already-published artifact,
    # downloaded by the orchestrator before invoking the producer (R4).
    artifacts: dict[str, Path] = field(default_factory=dict)
