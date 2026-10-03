"""
cleaner.py — Deletion engine.

Takes a list of FileEntry objects and deletes them safely,
logging every action and collecting errors.
"""

import logging
import os
import shutil
from dataclasses import dataclass, field
from pathlib import Path

from scanner import FileEntry

logger = logging.getLogger(__name__)


@dataclass
class CleanResult:
    deleted_paths: list[Path] = field(default_factory=list)
    freed_bytes: int = 0
    errors: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Safety guardrails
# ---------------------------------------------------------------------------

# Absolute paths that must never be deleted, no matter what
PROTECTED = {
    "/",
    "/root",
    "/home",
    "/etc",
    "/usr",
    "/bin",
    "/sbin",
    "/lib",
    "/lib64",
    "/boot",
    "/root/DISK-CLEANER",
    "/root/TVcidade10",   # protect the running project
}

# Paths under PROTECTED that ARE safe to clean (exceptions to the block above)
PROTECTED_EXCEPTIONS = {
    "/root/.cache",
    "/root/.npm",
    "/root/.local/share",
    "/root/aJOB-sda2",           # old project snapshots on sda2
    "/root/AI-models",           # AI app bundles — node_modules inside them are safe
    "/root/.antigravity-ide",    # IDE extensions cache
    "/usr/local/lib/python3.13/dist-packages",  # pyc caches in dist-packages
    "/usr/local/lib/python3.12/dist-packages",
    "/usr/local/lib/python3.11/dist-packages",
}


def _is_protected(path: Path) -> bool:
    s = str(path.resolve())
    # Check exceptions first (allowed sub-paths of protected roots)
    for exc in PROTECTED_EXCEPTIONS:
        if s == exc or s.startswith(exc + "/"):
            return False
    # Then check protected roots
    for p in PROTECTED:
        if s == p or s.startswith(p + "/"):
            return True
    return False


# ---------------------------------------------------------------------------
# Deletion
# ---------------------------------------------------------------------------

def _delete_one(path: Path) -> tuple[bool, str]:
    """
    Delete a single file or directory tree.
    Returns (success, error_message).
    """
    if _is_protected(path):
        return False, f"PROTECTED — skipped: {path}"
    try:
        if path.is_dir() and not path.is_symlink():
            shutil.rmtree(path)
        else:
            path.unlink(missing_ok=True)
        return True, ""
    except PermissionError as e:
        return False, f"Permission denied: {path} — {e}"
    except OSError as e:
        return False, f"OS error deleting {path}: {e}"


def clean_entries(
    entries: list[FileEntry],
    dry_run: bool = False,
    progress_cb=None,
) -> CleanResult:
    """
    Delete each entry.

    dry_run=True  → logs what would be deleted without touching the disk.
    progress_cb(path, freed_bytes, error) called after each item.
    """
    result = CleanResult()

    for entry in entries:
        path = entry.path

        if _is_protected(path):
            msg = f"PROTECTED — skipped: {path}"
            logger.warning(msg)
            result.errors.append(msg)
            if progress_cb:
                progress_cb(path, 0, msg)
            continue

        if dry_run:
            logger.info("[DRY-RUN] would delete %s (%s)", path, _fmt(entry.size))
            result.deleted_paths.append(path)
            result.freed_bytes += entry.size
            if progress_cb:
                progress_cb(path, entry.size, None)
            continue

        ok, err = _delete_one(path)
        if ok:
            logger.info("Deleted %s (%s)", path, _fmt(entry.size))
            result.deleted_paths.append(path)
            result.freed_bytes += entry.size
            if progress_cb:
                progress_cb(path, entry.size, None)
        else:
            logger.warning(err)
            result.errors.append(err)
            if progress_cb:
                progress_cb(path, 0, err)

    return result


# ---------------------------------------------------------------------------
# Convenience wrappers for special cleaners that use system commands
# ---------------------------------------------------------------------------

def clean_apt_cache(dry_run: bool = False) -> CleanResult:
    """Run apt-get clean / autoclean."""
    import subprocess
    result = CleanResult()
    cmds = (
        ["apt-get", "clean"] if not dry_run else ["apt-get", "--dry-run", "clean"],
        ["apt-get", "autoclean", "-y"] if not dry_run else ["apt-get", "--dry-run", "autoclean"],
    )
    for cmd in cmds:
        try:
            out = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            logger.info("apt: %s", out.stdout.strip() or "(no output)")
            if out.returncode != 0:
                result.errors.append(out.stderr.strip())
        except FileNotFoundError:
            result.errors.append("apt-get not found")
            break
        except Exception as e:
            result.errors.append(str(e))
    return result


def clean_docker_cache(dry_run: bool = False) -> CleanResult:
    """Run docker system prune."""
    import subprocess
    result = CleanResult()
    cmd = ["docker", "system", "prune", "-f"]
    if dry_run:
        cmd = ["docker", "system", "df"]
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        logger.info("docker: %s", out.stdout[:500])
        if out.returncode != 0:
            result.errors.append(out.stderr.strip())
    except FileNotFoundError:
        result.errors.append("docker not found — skipped")
    except Exception as e:
        result.errors.append(str(e))
    return result


# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------

def _fmt(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024:
            return f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} PB"


def fmt_bytes(n: int) -> str:
    return _fmt(n)
