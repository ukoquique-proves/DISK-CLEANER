# Disk Cleaner

Scans the filesystem for junk files and reclaims disk space. No third-party
dependencies — runs on any Python 3.10+ installation.

## What it cleans

| Category | Target |
|---|---|
| pip cache | `~/.cache/pip` |
| HuggingFace model cache | `~/.cache/huggingface` |
| PyTorch / Torch Hub cache | `~/.cache/torch` |
| npm cache | `~/.npm/_cacache` |
| APT package cache | `/var/cache/apt/archives/*.deb` |
| APT lists (stale) | `/var/cache/apt/archives/partial` |
| /tmp files | Files older than 2 days |
| Log files | `*.log` older than 7 days in `/var/log` |
| Python bytecode cache | `__pycache__` / `*.pyc` in system lib paths |
| Unused virtual environments | `venv` / `.venv` dirs not touched in 30+ days |
| Docker overlay / build cache | `/var/lib/docker/overlay2` dangling layers |
| Core dumps | `core`, `*.core`, `*.dump` in crash dirs |
| macOS metadata | `.DS_Store`, `Thumbs.db` |
| Editor backup files | `*~`, `*.bak`, `*.swp`, `*.orig` |
| Whisper model cache | Large `*.bin` / `*.safetensors` ASR model files |
| node_modules directories | `node_modules` folders not touched in 14+ days |

## Usage

```bash
# Interactive TUI (recommended)
./run.sh

# Scan only — report sizes, no deletion
./run.sh --scan

# Preview what would be deleted (safe)
./run.sh --dry-run

# Clean all categories without prompts
./run.sh --clean

# Target specific categories
./run.sh --dry-run --category pip_cache npm_cache node_modules

# List all available category IDs
./run.sh --list
```

Or call Python directly:

```bash
python3 main.py --scan
python3 main.py --dry-run --category pip_cache
python3 main.py --clean
```

## Interactive TUI

Running `./run.sh` (no flags) launches a menu-driven interface:

1. Full or selective scan with a live spinner
2. Per-category breakdown with sizes
3. Toggle checkboxes to pick what to clean
4. Dry-run preview showing sample paths
5. Confirmation prompt before any deletion
6. Summary with freed space

## Files

```
CLEANER-/
├── main.py        Entry point — CLI flags + launches TUI
├── rules.py       16 cleaning rule definitions
├── scanner.py     Filesystem walker (respects age, depth, filters)
├── cleaner.py     Deletion engine with safety guardrails
├── ui.py          Interactive terminal UI
├── run.sh         Launcher script
└── README.md      This file
```

## Safety

- `/root/DISK-CLEANER`, `/root/TVcidade10`, `/etc`, `/usr`, `/bin`, `/boot`
  and other system roots are permanently protected and will never be deleted.
- `/mnt` and `/media` are never entered (avoids walking mounted disks).
- Deletion requires an explicit confirmation prompt in interactive mode,
  or the `--clean` flag in CLI mode.
- `--dry-run` always shows exactly what would be removed before committing.

## Requirements

Python 3.10 or newer. No pip installs needed — everything uses the standard library.
