"""
main.py — Entry point for the Disk Cleaner.

Usage:
    python main.py              # interactive TUI
    python main.py --scan       # scan only, print report, no deletion
    python main.py --clean      # scan + clean all categories non-interactively
    python main.py --dry-run    # scan + show what would be deleted
    python main.py --category pip_cache huggingface_cache   # target specific rules
    python main.py --list       # list all available rule IDs
"""

import argparse
import logging
import sys
from pathlib import Path


def _setup_logging(verbose: bool):
    level = logging.DEBUG if verbose else logging.WARNING
    logging.basicConfig(
        level=level,
        format="%(asctime)s  %(levelname)-8s  %(name)s — %(message)s",
        datefmt="%H:%M:%S",
    )


def _list_rules():
    from rules import RULES
    print(f"\n  {'ID':<25} {'Label':<35} Description")
    print("  " + "─" * 90)
    for r in RULES:
        print(f"  {r.id:<25} {r.label:<35} {r.description}")
    print()


def _cli_scan(rules_subset=None) -> list:
    from rules import RULES
    from scanner import scan_rule
    from cleaner import fmt_bytes

    targets = rules_subset or RULES
    results = []
    grand = 0
    print(f"\n  Scanning {len(targets)} categories…\n")
    for rule in targets:
        r = scan_rule(rule)
        results.append(r)
        if r.total_bytes:
            grand += r.total_bytes
            print(f"  {r.rule.label:<35} {r.count:>6} items   {fmt_bytes(r.total_bytes)}")
        else:
            print(f"  {r.rule.label:<35}  (clean)")

    print(f"\n  Total reclaimable: {fmt_bytes(grand)}\n")
    return results


def _cli_clean(results, dry_run: bool = False):
    from cleaner import clean_entries, fmt_bytes

    entries = [e for r in results for e in r.entries]
    if not entries:
        print("  Nothing to clean.")
        return

    prefix = "[DRY-RUN] " if dry_run else ""
    print(f"\n  {prefix}Cleaning {len(entries)} items…\n")

    result = clean_entries(entries, dry_run=dry_run)
    print(f"\n  {prefix}Freed: {fmt_bytes(result.freed_bytes)}")
    if result.errors:
        print(f"  Errors ({len(result.errors)}):")
        for e in result.errors[:10]:
            print(f"    {e}")


def main():
    parser = argparse.ArgumentParser(
        description="Disk Cleaner — remove junk files from the system",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--scan", action="store_true", help="Scan and report only")
    parser.add_argument("--clean", action="store_true", help="Scan and clean without prompts")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be deleted")
    parser.add_argument("--category", nargs="+", metavar="ID", help="Only process these rule IDs")
    parser.add_argument("--list", action="store_true", help="List all rule IDs and exit")
    parser.add_argument("--verbose", "-v", action="store_true", help="Debug logging")
    args = parser.parse_args()

    _setup_logging(args.verbose)

    if args.list:
        _list_rules()
        return

    rules_subset = None
    if args.category:
        from rules import RULE_MAP
        rules_subset = []
        for cat in args.category:
            r = RULE_MAP.get(cat)
            if r:
                rules_subset.append(r)
            else:
                print(f"  Unknown category: {cat!r}  (use --list to see valid IDs)")
                sys.exit(1)

    if args.scan:
        _cli_scan(rules_subset)
        return

    if args.clean or args.dry_run:
        results = _cli_scan(rules_subset)
        _cli_clean(results, dry_run=args.dry_run)
        return

    # Default: interactive TUI
    from ui import main as tui_main
    tui_main()


if __name__ == "__main__":
    main()
