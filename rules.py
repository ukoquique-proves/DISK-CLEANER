"""
rules.py — Cleaning rule definitions.

Each rule describes a category of junk to scan for.
Rules are used by scanner.py to find candidates and report sizes.
"""

import os
import fnmatch
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable


@dataclass
class Rule:
    id: str                          # short key used in CLI flags
    label: str                       # human-readable category name
    description: str                 # one-line explanation shown in UI
    paths: list[str]                 # glob-expanded root paths to scan
    patterns: list[str] = field(default_factory=list)   # filename/glob patterns
    min_age_days: int = 0            # only files older than this
    recursive: bool = True
    # Optional extra filter: receives Path, returns True to include
    extra_filter: Callable[[Path], bool] | None = field(default=None, repr=False)


def _home(sub: str) -> str:
    return str(Path.home() / sub)


# ---------------------------------------------------------------------------
# Rule catalogue
# ---------------------------------------------------------------------------

RULES: list[Rule] = [

    Rule(
        id="pip_cache",
        label="pip cache",
        description="Cached pip wheel/package downloads",
        paths=[_home(".cache/pip")],
        patterns=["*"],
        recursive=True,
    ),

    Rule(
        id="huggingface_cache",
        label="HuggingFace model cache",
        description="Downloaded transformer models and tokenizers (~GB each)",
        paths=[_home(".cache/huggingface")],
        patterns=["*"],
        recursive=True,
    ),

    Rule(
        id="torch_cache",
        label="PyTorch / Torch Hub cache",
        description="Cached torch hub repos and compiled kernels",
        paths=[_home(".cache/torch")],
        patterns=["*"],
        recursive=True,
    ),

    Rule(
        id="npm_cache",
        label="npm cache",
        description="Node.js package manager cache",
        paths=[_home(".npm/_cacache"), _home(".npm/cache")],
        patterns=["*"],
        recursive=False,   # flat: delete top-level dirs inside cache
    ),

    Rule(
        id="apt_cache",
        label="APT package cache",
        description="Downloaded .deb packages no longer needed",
        paths=["/var/cache/apt/archives"],
        patterns=["*.deb", "*.deb.gz"],
        recursive=False,
    ),

    Rule(
        id="apt_lists",
        label="APT lists (stale)",
        description="Old APT package index files",
        paths=["/var/cache/apt/archives/partial"],
        patterns=["*"],
        recursive=True,
        min_age_days=7,
    ),

    Rule(
        id="tmp_files",
        label="/tmp files",
        description="Temporary files in /tmp older than 2 days",
        paths=["/tmp"],
        patterns=["*"],
        recursive=True,
        min_age_days=2,
    ),

    Rule(
        id="log_files",
        label="Log files",
        description="*.log files older than 7 days",
        paths=["/var/log"],
        patterns=["*.log", "*.log.*", "*.gz"],
        recursive=True,
        min_age_days=7,
    ),

    Rule(
        id="pyc_files",
        label="Python bytecode cache",
        description="Compiled .pyc files and __pycache__ directories",
        paths=["/usr/local/lib/python3.11", "/usr/local/lib/python3.12",
               "/usr/local/lib/python3.13", "/opt"],
        patterns=["*.pyc", "__pycache__"],
        recursive=True,
    ),
    Rule(
        id="venv_old",
        label="Unused virtual environments",
        description="Python venv directories not accessed in 30+ days",
        paths=["/root/TVcidade10", "/root/DISK-CLEANER", "/opt", "/home"],
        patterns=["venv", ".venv", "env"],
        recursive=True,
        min_age_days=30,
        extra_filter=lambda p: (p / "pyvenv.cfg").exists(),
    ),

    Rule(
        id="docker_overlay",
        label="Docker overlay / build cache",
        description="Dangling Docker layers and build cache",
        paths=["/var/lib/docker/overlay2", "/var/lib/docker/tmp"],
        patterns=["*"],
        recursive=False,
        extra_filter=lambda p: p.is_dir(),
    ),

    Rule(
        id="core_dumps",
        label="Core dumps",
        description="Crash core dump files",
        paths=["/tmp", "/var/crash"],
        patterns=["core", "core.*", "*.core", "*.dump"],
        recursive=True,
    ),

    Rule(
        id="ds_store",
        label="macOS metadata (.DS_Store)",
        description=".DS_Store and Thumbs.db files (macOS/Windows artifacts)",
        paths=["/home"],
        patterns=[".DS_Store", "Thumbs.db", "desktop.ini"],
        recursive=True,
    ),

    Rule(
        id="backup_files",
        label="Editor backup files",
        description="Tilde-backup, .bak, .swp, .orig files left by editors",
        paths=["/home", "/etc", "/opt"],
        patterns=["*~", "*.bak", "*.swp", "*.swo", "*.orig"],
        recursive=True,
    ),

    Rule(
        id="whisper_cache",
        label="Whisper / faster-whisper model cache",
        description="Locally downloaded Whisper ASR model files",
        paths=[_home(".cache/whisper"), _home(".cache/faster_whisper"),
               _home(".cache/huggingface/hub")],
        patterns=["*.bin", "*.pt", "*.gguf", "model.safetensors"],
        recursive=True,
        extra_filter=lambda p: p.stat().st_size > 50 * 1024 * 1024,  # >50 MB
    ),

    Rule(
        id="node_modules",
        label="node_modules directories",
        description="node_modules folders not touched in 14+ days",
        paths=["/root/aJOB-sda2", "/root/AI-models", "/root/.antigravity-ide",
               "/home", "/opt"],
        patterns=["node_modules"],
        recursive=True,
        min_age_days=14,
        extra_filter=lambda p: p.is_dir(),
    ),
]

RULE_MAP: dict[str, Rule] = {r.id: r for r in RULES}


def get_rule(rule_id: str) -> Rule | None:
    return RULE_MAP.get(rule_id)
