"""
scanner.py — Filesystem scanning engine.

For each Rule, walks the target paths and collects matching files/dirs,
respecting min_age_days and extra_filter.  Returns ScanResult objects
that the UI can present and the cleaner can act on.
"""

import fnmatch
import logging
import os
import time
from dataclasses import dataclass, field
from pathlib import Path

from rules import Rule, RULES

logger = logging.getLogger(__name__)

SKIP_DIRS = {
    "/proc", "/sys", "/dev", "/run", "/mnt", "/media",
    "/root/DISK-CLEANER",              # never delete ourselves
    "/root/TVcidade10/tv10-/venv",     # the running project's venv
    "/root/TVcidade10",                # protect the running project tree
}


@dataclass
class FileEntry:
    path: Path
    size: int        # bytes
    mtime: float     # epoch seconds


@dataclass
class ScanResult:
    rule: Rule
    entries: list[FileEntry] = field(default_factory=list)
    scan_errors: list[str] = field(default_factory=list)

    @property
    def total_bytes(self) -> int:
        return sum(e.size for e in self.entries)

    @property
    def count(self) -> int:
        return len(self.entries)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _dir_size(path: Path) -> int:
    """Recursively sum file sizes under a directory."""
    total = 0
    try:
        for entry in os.scandir(path):
            try:
                if entry.is_dir(follow_symlinks=False):
                    total += _dir_size(Path(entry.path))
                else:
                    total += entry.stat(follow_symlinks=False).st_size
            except OSError:
                pass
    except OSError:
        pass
    return total


def _entry_size(path: Path) -> int:
    try:
        if path.is_dir():
            return _dir_size(path)
        return path.stat().st_size
    except OSError:
        return 0


def _mtime(path: Path) -> float:
    try:
        return path.stat().st_mtime
    except OSError:
        return 0.0


def _age_days(path: Path) -> float:
    mt = _mtime(path)
    if mt == 0:
        return 0.0
    return (time.time() - mt) / 86400


def _matches_pattern(name: str, patterns: list[str]) -> bool:
    if not patterns:
        return True
    return any(fnmatch.fnmatch(name, p) for p in patterns)


def _should_skip(path: Path) -> bool:
    s = str(path)
    return any(s == skip or s.startswith(skip + "/") for skip in SKIP_DIRS)


# ---------------------------------------------------------------------------
# Core scanner
# ---------------------------------------------------------------------------

def scan_rule(rule: Rule, progress_cb=None) -> ScanResult:
    """
    Scan a single rule and return a ScanResult.
    progress_cb(path_str) is called for each directory entered (for UI feedback).
    """
    result = ScanResult(rule=rule)
    now = time.time()
    cutoff = now - rule.min_age_days * 86400

    for root_str in rule.paths:
        root = Path(root_str)
        if not root.exists():
            continue
        if _should_skip(root):
            continue

        if rule.recursive:
            _scan_recursive(root, rule, cutoff, result, progress_cb, depth=0)
        else:
            _scan_flat(root, rule, cutoff, result)

    return result


def _scan_flat(root: Path, rule: Rule, cutoff: float, result: ScanResult) -> None:
    try:
        for entry in os.scandir(root):
            p = Path(entry.path)
            if _should_skip(p):
                continue
            name = p.name
            if not _matches_pattern(name, rule.patterns):
                continue
            try:
                mt = entry.stat(follow_symlinks=False).st_mtime
            except OSError:
                continue
            if rule.min_age_days and mt > cutoff:
                continue
            if rule.extra_filter and not rule.extra_filter(p):
                continue
            size = _entry_size(p)
            result.entries.append(FileEntry(path=p, size=size, mtime=mt))
    except PermissionError as e:
        result.scan_errors.append(str(e))
    except OSError as e:
        result.scan_errors.append(str(e))


def _scan_recursive(
    root: Path,
    rule: Rule,
    cutoff: float,
    result: ScanResult,
    progress_cb,
    depth: int,
    max_depth: int = 8,
) -> None:
    if depth > max_depth:
        return
    if _should_skip(root):
        return
    if progress_cb:
        progress_cb(str(root))

    try:
        entries = list(os.scandir(root))
    except (PermissionError, OSError) as e:
        result.scan_errors.append(str(e))
        return

    for entry in entries:
        p = Path(entry.path)
        if _should_skip(p):
            continue
        name = p.name

        # Check if the name matches a pattern
        if _matches_pattern(name, rule.patterns):
            try:
                st = entry.stat(follow_symlinks=False)
                mt = st.st_mtime
            except OSError:
                continue
            if rule.min_age_days and mt > cutoff:
                # Age check on directory: use the mtime of the dir itself
                pass
            if rule.extra_filter and not rule.extra_filter(p):
                # Still recurse into directories that don't match the filter
                if entry.is_dir(follow_symlinks=False):
                    _scan_recursive(p, rule, cutoff, result, progress_cb, depth + 1, max_depth)
                continue
            if rule.min_age_days and mt > cutoff:
                if entry.is_dir(follow_symlinks=False):
                    _scan_recursive(p, rule, cutoff, result, progress_cb, depth + 1, max_depth)
                continue
            size = _entry_size(p)
            result.entries.append(FileEntry(path=p, size=size, mtime=mt))
            # Don't recurse into matched dirs (they'll be deleted wholesale)
            continue

        # Recurse into non-matching directories
        if entry.is_dir(follow_symlinks=False):
            _scan_recursive(p, rule, cutoff, result, progress_cb, depth + 1, max_depth)


def scan_all(rules: list[Rule] | None = None, progress_cb=None) -> list[ScanResult]:
    """Scan all (or a subset of) rules. Returns list of ScanResult."""
    targets = rules or RULES
    results = []
    for rule in targets:
        r = scan_rule(rule, progress_cb=progress_cb)
        results.append(r)
    return results
