"""Small append-only experiment ledger for concurrent solver wakes.

The interface is intentionally narrow::

    explog QUERY
    explog show ID...
    explog running
    explog add ...

Search scans record text directly. Running records reserve an object and exact
operation; result records close named reservations with explicit coverage.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sys

from solver import explog

SNIPPET_LENGTH = 240


def parse_entry_id(value: str) -> int | str:
    value = str(value).strip()
    if value.isdigit():
        return int(value)
    if explog.HANDLE.fullmatch(value):
        return value
    raise argparse.ArgumentTypeError("entry id is an integer or wake-name:sequence")


def compact(value: object, length: int = SNIPPET_LENGTH) -> str:
    text = " ".join(str(value or "").split())
    return text[:length] + (" …" if len(text) > length else "")


def compact_entry(entry: dict) -> str:
    campaign = entry.get("campaign") or "uncategorized"
    return (
        f"#{entry.get('id')} [{entry.get('verdict')}] "
        f"{campaign}: {compact(entry.get('object'))}"
    )


def render_full(entries: list[dict]) -> None:
    if not entries:
        print("no entries")
        return
    for entry in entries:
        print(compact_entry(entry))
        for key, value in entry.items():
            if key in {"id", "verdict", "campaign", "object"} or value in (None, "", [], {}):
                continue
            if isinstance(value, (dict, list)):
                value = json.dumps(value, ensure_ascii=False, sort_keys=True)
            print(f"    {key}: {value}")


def render_matches(matches: list[dict], total: int) -> None:
    if not matches:
        print("no matching Explog entries")
        return
    for entry in matches:
        print(compact_entry(entry))
        detail = entry.get("result") or entry.get("operation") or entry.get("coverage")
        if detail:
            print(f"    {compact(detail)}")
    print(f"{len(matches)} of {total} matching entries", file=sys.stderr)


def match_payload(matches: list[dict], total: int, query: str) -> dict:
    fields = (
        "id", "verdict", "campaign", "route", "object", "operation",
        "coverage", "result",
    )
    return {
        "query": query,
        "hits": total,
        "shown": len(matches),
        "results": [
            {name: entry.get(name) for name in fields if entry.get(name) not in (None, "")}
            for entry in matches
        ],
    }


def warn_active_duplicates(entries: list[dict]) -> None:
    for warning in explog.active_duplicate_errors(entries):
        print(f"warning: {warning}", file=sys.stderr)


def warn_reference_drift(entries: list[dict], ledger: explog.Ledger) -> None:
    for warning in explog.reference_warnings(entries, root=ledger.root):
        print(f"warning: {warning}", file=sys.stderr)


def _add_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="explog add", description="Append one ledger record")
    parser.add_argument("--verdict", choices=explog.VERDICTS, required=True)
    parser.add_argument("--campaign", default="")
    parser.add_argument("--route", default="")
    parser.add_argument("--object", dest="claim_object", default="")
    parser.add_argument("--operation", default="")
    parser.add_argument("--decision", default="")
    parser.add_argument("--coverage", default="")
    parser.add_argument("--result", default="")
    parser.add_argument("--evidence", action="append", default=[])
    parser.add_argument("--resolves", action="append", type=parse_entry_id, default=[])
    return parser


def _show_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="explog show", description="Open records by id")
    parser.add_argument("ids", nargs="+", type=parse_entry_id)
    parser.add_argument("--json", action="store_true")
    return parser


def _running_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="explog running", description="List active locks")
    parser.add_argument("--json", action="store_true")
    return parser


def _query_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="explog", description="Search experiment records")
    parser.add_argument("query", nargs="+")
    parser.add_argument("--limit", type=int, default=explog.DEFAULT_LIMIT)
    parser.add_argument("--json", action="store_true")
    return parser


def _validate_add(
    args: argparse.Namespace, entries: list[dict], ledger: explog.Ledger,
    wake_id: str,
) -> tuple[bool, dict]:
    running = args.verdict == "running"
    if running:
        if not all((args.claim_object.strip(), args.operation.strip(), args.decision.strip())):
            print("a running claim needs --object, --operation and --decision", file=sys.stderr)
            return False, {}
        if any((args.coverage, args.result, args.evidence, args.resolves)):
            print("a running claim cannot contain result fields", file=sys.stderr)
            return False, {}
        route_error = explog.validate_route(args.route, root=ledger.root)
        if route_error:
            print(route_error, file=sys.stderr)
            return False, {}
        duplicate = explog.find_active_duplicate(
            entries, args.claim_object, args.operation,
        )
        if duplicate:
            print(f"operation already reserved by #{duplicate.get('id')}", file=sys.stderr)
            return False, {}
        return True, {
            "campaign": args.campaign.strip() or wake_id,
            "route": args.route.strip(),
            "object": args.claim_object.strip(),
            "operation": args.operation.strip(),
            "decision": args.decision.strip(),
        }

    if len(args.resolves) != 1:
        print("a result needs exactly one --resolves ID", file=sys.stderr)
        return False, {}
    overrides = [
        option for option, value in (
            ("--campaign", args.campaign),
            ("--route", args.route),
            ("--object", args.claim_object),
            ("--operation", args.operation),
            ("--decision", args.decision),
        )
        if value.strip()
    ]
    if overrides:
        print(
            "a result inherits claim identity; omit " + ", ".join(overrides),
            file=sys.stderr,
        )
        return False, {}
    target_id = args.resolves[0]
    if not args.coverage.strip():
        print("a result needs exact --coverage", file=sys.stderr)
        return False, {}
    if not args.result.strip():
        print("a result needs --result", file=sys.stderr)
        return False, {}
    if args.verdict != "blocked" and not args.evidence:
        print("a result needs at least one --evidence path", file=sys.stderr)
        return False, {}
    try:
        claim = explog.entries_by_id(entries, [target_id])[0]
    except ValueError as exc:
        print(exc, file=sys.stderr)
        return False, {}
    active_ids = {entry.get("id") for entry in explog.current(entries)}
    if claim.get("verdict") != "running":
        print("--resolves must name running claims", file=sys.stderr)
        return False, {}
    if target_id not in active_ids:
        print(f"claim already resolved: {target_id}", file=sys.stderr)
        return False, {}
    evidence: list[str] = []
    if args.evidence:
        evidence, evidence_error = explog.validated_evidence(
            args.evidence, root=ledger.root,
        )
        if evidence_error:
            print(evidence_error, file=sys.stderr)
            return False, {}
    values = {
        "campaign": claim.get("campaign") or wake_id,
        "route": claim.get("route", ""),
        "object": claim.get("object", ""),
        "operation": claim.get("operation", ""),
        "decision": claim.get("decision", ""),
        "coverage": args.coverage.strip(),
        "result": args.result.strip(),
        "resolves": target_id,
    }
    if evidence:
        values["evidence"] = evidence
    return True, values


def add(args: argparse.Namespace, ledger: explog.Ledger) -> int:
    wake_id = explog.current_wake_id(root=ledger.root)
    target = ledger.shard(wake_id)
    ledger.shard_dir.mkdir(parents=True, exist_ok=True)
    with ledger.lock_path.open("a+", encoding="utf-8") as lock_file, \
            explog.locked(lock_file):
        bad: list[str] = []
        entries = ledger.read(bad)
        if bad:
            print("refusing to append while log records are unreadable", file=sys.stderr)
            return 2
        errors = explog.lifecycle_errors(entries)
        if errors:
            print(f"refusing to append: {errors[0]}", file=sys.stderr)
            return 2
        warn_reference_drift(entries, ledger)
        warn_active_duplicates(entries)
        valid, values = _validate_add(args, entries, ledger, wake_id)
        if not valid:
            return 2
        entry = {
            "id": explog.next_id(entries, wake_id),
            "created_at": dt.datetime.now(dt.UTC).isoformat(timespec="seconds"),
            "verdict": args.verdict,
            **{key: value for key, value in values.items() if value not in (None, "", [], {})},
            "log_path": ledger.display(target),
        }
        explog.append_line(target, entry)
    print(compact_entry(entry))
    return 0


def _help() -> None:
    print(__doc__.strip())


def _one_edit_apart(value: str, candidate: str) -> bool:
    """Return whether one insertion, deletion or substitution separates words."""
    if abs(len(value) - len(candidate)) > 1 or value == candidate:
        return False
    if len(value) == len(candidate):
        return sum(left != right for left, right in zip(value, candidate, strict=True)) == 1
    shorter, longer = (value, candidate) if len(value) < len(candidate) else (candidate, value)
    short_index = long_index = differences = 0
    while short_index < len(shorter) and long_index < len(longer):
        if shorter[short_index] == longer[long_index]:
            short_index += 1
        else:
            differences += 1
            if differences > 1:
                return False
        long_index += 1
    return True


def _likely_command_typo(value: str) -> str | None:
    token = value.casefold()
    if not re.fullmatch(r"[a-z]+", token):
        return None
    return next((name for name in ("add", "show", "running")
                 if _one_edit_apart(token, name)), None)


def main(argv: list[str] | None = None, ledger: explog.Ledger | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    ledger = explog.DEFAULT if ledger is None else ledger
    if not argv or argv[0] in {"-h", "--help"}:
        _help()
        return 0
    try:
        command = argv[0]
        if command == "add":
            return add(_add_parser().parse_args(argv[1:]), ledger)
        typo = _likely_command_typo(command)
        if typo:
            raise ValueError(f"unknown command {command!r}; did you mean {typo!r}?")
        bad: list[str] = []
        entries = ledger.read(bad)
        if bad:
            print(
                "warning: some Explog records were unreadable; showing readable records",
                file=sys.stderr,
            )
        for error in explog.lifecycle_errors(entries):
            print(f"warning: invalid Explog ledger: {error}", file=sys.stderr)
        warn_reference_drift(entries, ledger)
        warn_active_duplicates(entries)
        if command == "show":
            args = _show_parser().parse_args(argv[1:])
            selected = explog.entries_by_id(entries, args.ids)
            if args.json:
                json.dump(selected, sys.stdout, ensure_ascii=False, indent=2)
                print()
            else:
                render_full(selected)
            return 0
        if command == "running":
            args = _running_parser().parse_args(argv[1:])
            selected = explog.current(entries)
            if args.json:
                json.dump(selected, sys.stdout, ensure_ascii=False, indent=2)
                print()
            else:
                render_full(selected)
            return 0
        args = _query_parser().parse_args(argv)
        if args.limit < 1:
            raise ValueError("--limit must be positive")
        query = " ".join(args.query)
        matches, total = explog.search_entries(entries, query, args.limit)
        if args.json:
            json.dump(
                match_payload(matches, total, query), sys.stdout,
                ensure_ascii=False, indent=2,
            )
            print()
        else:
            render_matches(matches, total)
        return 0
    except (SystemExit, ValueError) as exc:
        if isinstance(exc, ValueError):
            print(exc, file=sys.stderr)
            return 2
        return exc.code if isinstance(exc.code, int) else 2


if __name__ == "__main__":
    raise SystemExit(main())
