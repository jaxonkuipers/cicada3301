"""The experiment log: what was tried against the unsolved sections.

    python3 -m tools.explog add --section 0.5 --method "vigenere sweep" \\
        --params '{"key_len": "1-12", "skips": "none"}' \\
        --coverage "all 29^k keys for k<=3; dictionary keys for k<=12" \\
        --verdict disproved --notes "best fitness -3.9, indistinguishable from noise"
    python3 -m tools.explog list --section 0.5
    python3 -m tools.explog search vigenere

Search the Discord archive before claiming novelty (tools.dsearch); search
THIS log before re-running your own work. Every entry is one JSON line in
research/experiments.jsonl, append-only, committed to git.

Verdicts:
  running       logged at the START of a run, so parallel agents (which do not
                know about each other) can avoid duplicating work. Claim, then
                list: if an earlier running entry already covers your target,
                pick different work. Follow up with a final verdict when done;
                a running entry hours old with no follow-up is stale -- take it.
  disproved     the method is excluded for the stated coverage -- say exactly
                what keyspace was searched, or the claim is worthless
  abandoned     tried and stopped without exhausting anything; may be worth
                resuming, say why it stopped
  inconclusive  ran to completion but the result decides nothing
  promising     a signal worth a follow-up; record the numbers
  solved        rune-exact English for the stated section; log it, then keep
                logging -- the other sections are still unsolved

exit codes: 0 = fine (including an empty listing), 2 = bad arguments, or a
log too damaged to append to safely (see `add`).
"""

from __future__ import annotations

import argparse
import contextlib
import datetime as dt
import json
import os
import sys

try:
    import fcntl
except ImportError:  # not POSIX; the log still works, just without locking
    fcntl = None

from lib.paths import ROOT

LOG = ROOT / "research" / "experiments.jsonl"
VERDICTS = ("running", "disproved", "abandoned", "inconclusive", "promising", "solved")


@contextlib.contextmanager
def _locked(f):
    """Exclusive lock across read-ids-then-append, where the platform has one.

    Concurrent agents logging at once must neither mint the same id nor
    interleave partial lines. Without fcntl (Windows) the log still works,
    single-writer.

    The write is flushed BEFORE the lock drops. `with open(...) as f,
    _locked(f):` unwinds this manager first, so releasing here while the entry
    sat in the userspace buffer let the next process take the lock, read a log
    that did not contain the entry yet, and mint the same id -- measured, two
    concurrent adds both got #1. flush() is what closes that window (the other
    process reads through the same page cache); fsync() is for power loss.
    """
    if fcntl is None:
        yield
        f.flush()
        os.fsync(f.fileno())
        return
    fcntl.flock(f, fcntl.LOCK_EX)
    try:
        yield
        f.flush()
        os.fsync(f.fileno())
    finally:
        fcntl.flock(f, fcntl.LOCK_UN)


def read_log(bad: list[int] | None = None) -> list[dict]:
    """Entries, skipping unparseable lines with a warning.

    Pass `bad` to collect the line numbers that were skipped. Listing can live
    with a hole; `add` cannot -- see there.
    """
    if not LOG.exists():
        return []
    out = []
    for i, line in enumerate(LOG.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError as e:
            print(f"warning: {LOG.name}:{i} is not valid JSON: {e}", file=sys.stderr)
            if bad is not None:
                bad.append(i)
    return out


def known_sections() -> tuple[str, ...]:
    """Section ids from sections.csv, plus 'all'."""
    from lib import corpus

    return ("all", *(s.id for s in corpus.load().sections))


def add(args: argparse.Namespace) -> int:
    # The log is how agents that cannot see each other avoid duplicating work,
    # so a typo'd section is not a cosmetic problem: `--section 0.05` claims a
    # target nobody else is looking at, and `list --section 0.5` never shows it.
    valid = known_sections()
    if args.section not in valid:
        print(
            f"unknown section {args.section!r}; expected one of {', '.join(valid)}",
            file=sys.stderr,
        )
        return 2
    params = args.params
    if params:
        try:
            params = json.loads(params)
        except json.JSONDecodeError:
            pass  # keep as the free-text string it was
    LOG.parent.mkdir(exist_ok=True)
    with open(LOG, "a", encoding="utf-8") as f, _locked(f):
        bad: list[int] = []
        entries = read_log(bad)
        if bad:
            # An unreadable line may hold the highest id, so max(ids)+1 can
            # mint one that already exists. Ids are how agents that cannot see
            # each other refer to a claim, so a silent collision is worse than
            # refusing: repair the line, then log.
            print(
                f"refusing to append: {LOG.name} has unreadable lines "
                f"({', '.join(str(i) for i in bad)}), so the next id is unknown.\n"
                "  fix or delete those lines, then run this again.",
                file=sys.stderr,
            )
            return 2
        entry = {
            "id": max((e.get("id", 0) for e in entries), default=0) + 1,
            "ts": dt.datetime.now(dt.UTC).strftime("%Y-%m-%d %H:%M"),
            "section": args.section,
            "method": args.method,
            "params": params,
            "coverage": args.coverage,
            "verdict": args.verdict,
            "notes": args.notes,
        }
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    print(f"logged #{entry['id']} ({args.verdict}) to {LOG.relative_to(ROOT)}")
    return 0


def matches(e: dict, args: argparse.Namespace) -> bool:
    if getattr(args, "section", None) and e.get("section") != args.section:
        return False
    if getattr(args, "verdict", None) and e.get("verdict") != args.verdict:
        return False
    return True


def render(entries: list[dict], as_json: bool) -> None:
    if as_json:
        json.dump(entries, sys.stdout, ensure_ascii=False, indent=1)
        print()
        return
    if not entries:
        print("no entries")
        return
    for e in entries:
        print(f"#{e.get('id')}  {e.get('ts')}  {e.get('section')}  "
              f"[{e.get('verdict')}]  {e.get('method')}")
        for key in ("params", "coverage", "notes"):
            if e.get(key):
                print(f"      {key}: {e[key]}")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="python3 -m tools.explog",
        description="Append-only log of attacks on the unsolved sections.",
    )
    sub = ap.add_subparsers(dest="cmd", required=True)

    a = sub.add_parser("add", help="record an experiment")
    a.add_argument(
        "--section", required=True,
        help="a section id from sections.csv, e.g. 0.5, or 'all'",
    )
    a.add_argument("--method", required=True, help="what was run")
    a.add_argument("--params", default="", help="parameters, ideally JSON")
    a.add_argument("--coverage", default="", help="exactly what was searched")
    a.add_argument("--verdict", required=True, choices=VERDICTS)
    a.add_argument("--notes", default="", help="scores, observations, links")

    ls = sub.add_parser("list", help="list entries")
    ls.add_argument("--section", help="a section id from sections.csv, or 'all'")
    ls.add_argument("--verdict", choices=VERDICTS)
    ls.add_argument("--json", action="store_true")

    se = sub.add_parser("search", help="substring search across entries")
    se.add_argument("term")
    se.add_argument("--json", action="store_true")

    args = ap.parse_args(argv)
    if args.cmd == "add":
        return add(args)
    # Same validation as `add`, for the same reason pointing the other way:
    # `list --section 0.05` printed "no entries" and exited 0, and AGENTS.md
    # step 4 tells the next agent to read that as "nobody has claimed this,
    # take it". A typo must not manufacture an unclaimed target.
    if getattr(args, "section", None):
        valid = known_sections()
        if args.section not in valid:
            print(
                f"unknown section {args.section!r}; expected one of "
                f"{', '.join(valid)}",
                file=sys.stderr,
            )
            return 2
    entries = read_log()
    if args.cmd == "list":
        entries = [e for e in entries if matches(e, args)]
    else:
        t = args.term.lower()
        entries = [e for e in entries if t in json.dumps(e, ensure_ascii=False).lower()]
    render(entries, args.json)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
