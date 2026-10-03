"""
ui.py — Interactive terminal UI for the disk cleaner.

Provides a menu-driven interface:
  1. Full scan (all rules) with progress bar
  2. Per-category breakdown with sizes
  3. Select categories to clean (toggle checkboxes)
  4. Dry-run preview
  5. Confirm and execute deletion
  6. Summary report
"""

import os
import sys
import time
import threading
import shutil
from pathlib import Path

from rules import RULES, Rule
from scanner import scan_rule, ScanResult, FileEntry
from cleaner import clean_entries, clean_apt_cache, clean_docker_cache, fmt_bytes

# ---------------------------------------------------------------------------
# Terminal helpers
# ---------------------------------------------------------------------------

RESET  = "\033[0m"
BOLD   = "\033[1m"
DIM    = "\033[2m"
RED    = "\033[31m"
GREEN  = "\033[32m"
YELLOW = "\033[33m"
CYAN   = "\033[36m"
WHITE  = "\033[97m"
BG_DARK = "\033[48;5;234m"


def _supports_color() -> bool:
    return hasattr(sys.stdout, "isatty") and sys.stdout.isatty()


USE_COLOR = _supports_color()


def c(code: str, text: str) -> str:
    return f"{code}{text}{RESET}" if USE_COLOR else text


def _clear():
    os.system("clear" if os.name != "nt" else "cls")


def _cols() -> int:
    return shutil.get_terminal_size((80, 24)).columns


def _hr(char="─"):
    print(c(DIM, char * _cols()))


def _header():
    _clear()
    cols = _cols()
    title = "  DISK CLEANER  "
    pad = (cols - len(title)) // 2
    print(c(BOLD + CYAN, " " * pad + title))
    _hr("═")


def _disk_bar() -> str:
    stat = shutil.disk_usage("/")
    pct = stat.used / stat.total * 100
    bar_w = 30
    filled = int(bar_w * stat.used / stat.total)
    color = RED if pct > 85 else YELLOW if pct > 60 else GREEN
    bar = c(color, "█" * filled) + c(DIM, "░" * (bar_w - filled))
    return (
        f"  Disk: [{bar}] {pct:.1f}%  "
        f"used {fmt_bytes(stat.used)} / free {fmt_bytes(stat.free)} / total {fmt_bytes(stat.total)}"
    )


def _input(prompt: str) -> str:
    try:
        return input(c(CYAN, prompt)).strip()
    except (EOFError, KeyboardInterrupt):
        print()
        return ""


# ---------------------------------------------------------------------------
# Spinner (shown while scanning)
# ---------------------------------------------------------------------------

class Spinner:
    FRAMES = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"

    def __init__(self, label: str):
        self.label = label
        self._stop = threading.Event()
        self._current = ""
        self._thread = threading.Thread(target=self._spin, daemon=True)

    def update(self, text: str):
        self._current = text[-60:] if len(text) > 60 else text

    def _spin(self):
        i = 0
        while not self._stop.is_set():
            frame = self.FRAMES[i % len(self.FRAMES)]
            line = f"\r  {c(CYAN, frame)} {self.label}  {c(DIM, self._current)}"
            cols = _cols()
            print(line[:cols].ljust(cols), end="", flush=True)
            time.sleep(0.08)
            i += 1

    def __enter__(self):
        self._thread.start()
        return self

    def __exit__(self, *_):
        self._stop.set()
        self._thread.join()
        print("\r" + " " * _cols() + "\r", end="", flush=True)


# ---------------------------------------------------------------------------
# Scan
# ---------------------------------------------------------------------------

def run_scan(selected_rules: list[Rule] | None = None) -> list[ScanResult]:
    targets = selected_rules or RULES
    results: list[ScanResult] = []

    print(f"\n  Scanning {len(targets)} categor{'y' if len(targets)==1 else 'ies'}…\n")

    for i, rule in enumerate(targets):
        label = f"[{i+1}/{len(targets)}] {rule.label}"
        with Spinner(label) as sp:
            result = scan_rule(rule, progress_cb=sp.update)
        size_str = fmt_bytes(result.total_bytes)
        count_str = str(result.count)
        status = c(YELLOW, size_str) if result.total_bytes > 0 else c(GREEN, "clean")
        print(f"  {'✓' if result.total_bytes == 0 else '●'}  {rule.label:<35} {count_str:>6} items   {status}")
        results.append(result)

    print()
    return results


# ---------------------------------------------------------------------------
# Category selection
# ---------------------------------------------------------------------------

def select_categories(results: list[ScanResult]) -> list[ScanResult]:
    """Interactive toggle-list. Returns the subset the user wants to clean."""
    # Only show rules that found something
    nonempty = [r for r in results if r.count > 0]
    if not nonempty:
        return []

    selected = set(range(len(nonempty)))  # all selected by default

    while True:
        _header()
        print(_disk_bar())
        print()
        print(c(BOLD, "  Select categories to clean  ") + c(DIM, "(toggle with number, A=all, N=none, Enter=continue)"))
        print()

        total_selected = 0
        for i, r in enumerate(nonempty):
            checked = i in selected
            box = c(GREEN, "[✓]") if checked else c(DIM, "[ ]")
            size = fmt_bytes(r.total_bytes)
            label = r.rule.label
            desc = r.rule.description
            if checked:
                total_selected += r.total_bytes
            print(f"  {box} {c(BOLD, str(i+1)):>4}.  {label:<35} {c(YELLOW, size):>12}   {c(DIM, desc)}")

        print()
        _hr()
        print(f"  Total selected: {c(YELLOW + BOLD, fmt_bytes(total_selected))}")
        _hr()

        choice = _input("\n  > ").upper()

        if choice == "":
            break
        elif choice == "A":
            selected = set(range(len(nonempty)))
        elif choice == "N":
            selected = set()
        else:
            for ch in choice.replace(",", " ").split():
                try:
                    idx = int(ch) - 1
                    if 0 <= idx < len(nonempty):
                        if idx in selected:
                            selected.discard(idx)
                        else:
                            selected.add(idx)
                except ValueError:
                    pass

    return [nonempty[i] for i in sorted(selected)]


# ---------------------------------------------------------------------------
# Preview / dry-run
# ---------------------------------------------------------------------------

def show_preview(chosen: list[ScanResult]):
    _header()
    print(_disk_bar())
    print()
    print(c(BOLD, "  DRY-RUN PREVIEW  ") + c(DIM, "(nothing deleted yet)"))
    print()

    grand_total = 0
    for r in chosen:
        print(c(BOLD, f"  {r.rule.label}") + f"  ({fmt_bytes(r.total_bytes)})")
        # show up to 8 sample entries
        for e in r.entries[:8]:
            print(c(DIM, f"    {e.path}"))
        if r.count > 8:
            print(c(DIM, f"    … and {r.count - 8} more"))
        grand_total += r.total_bytes
        print()

    _hr()
    print(f"  {c(BOLD, 'Total to free:')}  {c(YELLOW + BOLD, fmt_bytes(grand_total))}")
    _hr()


# ---------------------------------------------------------------------------
# Execute cleaning
# ---------------------------------------------------------------------------

def run_clean(chosen: list[ScanResult], dry_run: bool = False) -> int:
    all_entries: list[FileEntry] = []
    apt_needed = any(r.rule.id in ("apt_cache", "apt_lists") for r in chosen)
    docker_needed = any(r.rule.id == "docker_overlay" for r in chosen)

    for r in chosen:
        if r.rule.id in ("apt_cache", "apt_lists"):
            continue   # handled separately
        if r.rule.id == "docker_overlay":
            continue
        all_entries.extend(r.entries)

    freed = 0
    errors: list[str] = []
    done = 0

    print(f"\n  {'[DRY-RUN] ' if dry_run else ''}Cleaning {len(all_entries)} items…\n")

    def _cb(path, size, err):
        nonlocal freed, done
        done += 1
        if err:
            errors.append(err)
            print(c(RED, f"  ✗ {err[:80]}"))
        else:
            freed += size
            label = str(path)
            if len(label) > 65:
                label = "…" + label[-64:]
            print(c(DIM, f"  {'~' if dry_run else '✓'} {label}  {fmt_bytes(size)}"))

    result = clean_entries(all_entries, dry_run=dry_run, progress_cb=_cb)
    freed += result.freed_bytes if dry_run else 0

    if apt_needed:
        print(c(CYAN, "\n  Running apt-get clean…"))
        ar = clean_apt_cache(dry_run=dry_run)
        errors.extend(ar.errors)

    if docker_needed:
        print(c(CYAN, "\n  Running docker system prune…"))
        dr = clean_docker_cache(dry_run=dry_run)
        errors.extend(dr.errors)

    return result.freed_bytes


# ---------------------------------------------------------------------------
# Main flow
# ---------------------------------------------------------------------------

def confirm(prompt: str) -> bool:
    ans = _input(f"  {prompt} [y/N] ")
    return ans.lower() in ("y", "yes")


def main():
    _header()
    print(_disk_bar())
    print()
    print(c(BOLD, "  Welcome to Disk Cleaner"))
    print(c(DIM,  "  Scans for pip caches, model files, logs, temp files,"))
    print(c(DIM,  "  bytecode, old venvs, core dumps, and more.\n"))

    print(c(BOLD, "  Options:"))
    print("   1. Full scan (all categories)")
    print("   2. Quick scan (select categories first)")
    print("   Q. Quit")
    print()

    mode = _input("  > ")
    if mode.upper() == "Q" or mode == "":
        print("  Bye.")
        return

    if mode == "2":
        # Let user pick which rules to scan before scanning
        _header()
        print(c(BOLD, "  Choose categories to scan:\n"))
        for i, rule in enumerate(RULES):
            print(f"  {i+1:>2}.  {rule.label:<35} {c(DIM, rule.description)}")
        print()
        raw = _input("  Enter numbers (comma/space separated), or Enter for all: ")
        if raw.strip():
            selected_rules = []
            for tok in raw.replace(",", " ").split():
                try:
                    idx = int(tok) - 1
                    if 0 <= idx < len(RULES):
                        selected_rules.append(RULES[idx])
                except ValueError:
                    pass
            if not selected_rules:
                selected_rules = RULES
        else:
            selected_rules = RULES
    else:
        selected_rules = RULES

    # --- SCAN ---
    _header()
    print(_disk_bar())
    results = run_scan(selected_rules)

    nonempty = [r for r in results if r.count > 0]
    if not nonempty:
        print(c(GREEN + BOLD, "  ✓ Nothing to clean — your disk looks tidy!"))
        input(c(DIM, "\n  Press Enter to exit… "))
        return

    total = sum(r.total_bytes for r in nonempty)
    print(c(BOLD, f"  Found {fmt_bytes(total)} of reclaimable space across {len(nonempty)} categories.\n"))

    # --- SELECT ---
    chosen = select_categories(results)
    if not chosen:
        print(c(DIM, "\n  Nothing selected. Exiting."))
        return

    # --- PREVIEW ---
    show_preview(chosen)
    chosen_total = sum(r.total_bytes for r in chosen)

    print()
    if not confirm(f"Preview shown above. Run dry-run first?"):
        pass
    else:
        run_clean(chosen, dry_run=True)
        print()

    print()
    if not confirm(f"DELETE {fmt_bytes(chosen_total)} permanently? This cannot be undone."):
        print(c(DIM, "  Aborted."))
        return

    # --- CLEAN ---
    _header()
    print(_disk_bar())
    freed = run_clean(chosen, dry_run=False)

    # --- SUMMARY ---
    print()
    _hr("═")
    stat_after = shutil.disk_usage("/")
    print(c(GREEN + BOLD, f"  ✓ Done!  Freed approximately {fmt_bytes(freed)}"))
    print(f"  Disk now: {fmt_bytes(stat_after.free)} free of {fmt_bytes(stat_after.total)}")
    _hr("═")
    input(c(DIM, "\n  Press Enter to exit… "))


if __name__ == "__main__":
    main()
