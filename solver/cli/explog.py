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
import contextlib
import datetime as dt
import json
import os
import re
import subprocess
import sys
from pathlib import Path

try:
    import fcntl
except ImportError:  # pragma: no cover - Windows retains single-writer use
    fcntl = None

from solver.paths import ROOT

SHARD_DIR = ROOT / "research" / "explog"
LOG = SHARD_DIR
VERDICTS = ("running", "negative", "positive", "blocked")
INHERITED_FIELDS = ("campaign", "route", "object", "operation", "decision")
HANDLE = re.compile(r"^[a-z0-9][a-z0-9-]{0,95}:[1-9][0-9]*$")
TOKEN = re.compile(r"[^\W_]+", re.UNICODE)
DEFAULT_LIMIT = 100
SNIPPET_LENGTH = 240


def tokens(value: object) -> tuple[str, ...]:
    """Return unique case-folded words in original order."""
    if not isinstance(value, str):
        value = json.dumps(value, ensure_ascii=False, sort_keys=True)
    return tuple(dict.fromkeys(TOKEN.findall(value.casefold())))


def normalized(value: object) -> str:
    return " ".join(tokens(value))


def parse_entry_id(value: str) -> int | str:
    value = str(value).strip()
    if value.isdigit():
        return int(value)
    if HANDLE.fullmatch(value):
        return value
    raise argparse.ArgumentTypeError("entry id is an integer or wake-name:sequence")


def sharded_mode() -> bool:
    return LOG == SHARD_DIR


def log_paths() -> list[Path]:
    if not sharded_mode():
        return [LOG] if LOG.exists() else []
    return sorted(SHARD_DIR.glob("*.jsonl")) if SHARD_DIR.exists() else []


def entry_time(entry: dict) -> str:
    return str(entry.get("created_at") or entry.get("ts") or "")


def read_log(bad: list[str] | None = None) -> list[dict]:
    """Read all wake shards as one chronological record."""
    rows: list[tuple[str, int, dict]] = []
    serial = 0
    for path in log_paths():
        for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if not line.strip():
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError as exc:
                location = f"{path}:{line_number}"
                print(f"warning: {location} is not valid JSON: {exc}", file=sys.stderr)
                if bad is not None:
                    bad.append(location)
                continue
            if "log_path" not in entry:
                entry["log_path"] = _display_path(path)
            rows.append((entry_time(entry), serial, entry))
            serial += 1
    rows.sort(key=lambda row: (row[0], row[1]))
    return [entry for _, _, entry in rows]


def _display_path(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def current_wake_id(runner=subprocess.run) -> str:
    supplied = os.environ.get("CICADA_WAKE_ID", "").strip().casefold()
    if supplied:
        return supplied if re.fullmatch(r"[a-z0-9][a-z0-9-]{0,95}", supplied) else "local"
    try:
        result = runner(
            ["git", "branch", "--show-current"], cwd=ROOT, check=True,
            text=True, capture_output=True,
        )
        branch = result.stdout.strip().removeprefix("wake/")
    except (OSError, subprocess.CalledProcessError):
        branch = "local"
    return re.sub(r"[^a-z0-9-]+", "-", branch.casefold()).strip("-")[:96] or "local"


def write_log_path() -> tuple[Path, str]:
    if not sharded_mode():
        return LOG, ""
    wake_id = current_wake_id()
    return SHARD_DIR / f"{wake_id}.jsonl", wake_id


@contextlib.contextmanager
def locked(file):
    """Serialize a read/check/append transaction."""
    if fcntl is None:
        yield
        return
    fcntl.flock(file, fcntl.LOCK_EX)
    try:
        yield
    finally:
        fcntl.flock(file, fcntl.LOCK_UN)


def resolved_ids(entries: list[dict]) -> set[int | str]:
    resolved: set[int | str] = set()
    for entry in entries:
        values = entry.get("resolves") or []
        if not isinstance(values, list):
            values = [values]
        resolved.update(values)
    return resolved


def current(entries: list[dict]) -> list[dict]:
    """Return unresolved running locks."""
    resolved = resolved_ids(entries)
    return [
        entry for entry in entries
        if entry.get("verdict") == "running" and entry.get("id") not in resolved
    ]


def ledger_errors(entries: list[dict]) -> list[str]:
    """Return lifecycle violations in chronological ledger order."""
    errors: list[str] = []
    seen: dict[int | str, dict] = {}
    active: set[int | str] = set()
    for entry in entries:
        entry_id = entry.get("id")
        if entry_id in seen:
            errors.append(f"duplicate Explog id {entry_id}")
            continue
        if entry.get("verdict") == "running":
            duplicate = next((
                active_id for active_id in active
                if normalized(seen[active_id].get("object"))
                == normalized(entry.get("object"))
                and normalized(seen[active_id].get("operation"))
                == normalized(entry.get("operation"))
            ), None)
            if duplicate is not None:
                errors.append(
                    f"running claim {entry_id} duplicates active operation {duplicate}"
                )
            seen[entry_id] = entry
            active.add(entry_id)
            continue

        target_id = entry.get("resolves")
        if isinstance(target_id, list) or target_id in (None, ""):
            errors.append(f"result {entry_id} must resolve exactly one running ID")
        elif target_id not in seen:
            errors.append(f"result {entry_id} has a forward or unknown reference to {target_id}")
        else:
            target = seen[target_id]
            if target.get("verdict") != "running":
                errors.append(f"result {entry_id} resolves non-running record {target_id}")
            elif target_id not in active:
                errors.append(f"result {entry_id} resolves already closed claim {target_id}")
            else:
                active.remove(target_id)
            mismatched = [
                field for field in INHERITED_FIELDS
                if entry.get(field, "") != target.get(field, "")
            ]
            if mismatched:
                errors.append(
                    f"result {entry_id} differs from claim {target_id} in "
                    + ", ".join(mismatched)
                )
        seen[entry_id] = entry
    return errors


def entries_by_id(entries: list[dict], ids: list[int | str]) -> list[dict]:
    lookup = {entry.get("id"): entry for entry in entries}
    missing = [entry_id for entry_id in ids if entry_id not in lookup]
    if missing:
        raise ValueError("unknown Explog ids: " + ", ".join(map(str, missing)))
    return [lookup[entry_id] for entry_id in ids]


def _record_text(entry: dict) -> str:
    return json.dumps(entry, ensure_ascii=False, sort_keys=True)


def search_entries(
    entries: list[dict], query: str, limit: int = DEFAULT_LIMIT,
) -> tuple[list[dict], int]:
    """Search conclusions and unresolved locks, hiding superseded reservations."""
    query_terms = tokens(query)
    if not query_terms:
        raise ValueError("query contains no searchable terms")
    phrase = " ".join(query.split()).casefold()
    matches: list[tuple[bool, int, dict]] = []
    resolved = resolved_ids(entries)
    visible = [
        entry for entry in entries
        if entry.get("verdict") != "running" or entry.get("id") not in resolved
    ]
    for order, entry in enumerate(visible):
        text = _record_text(entry)
        text_terms = set(tokens(text))
        if all(term in text_terms for term in query_terms):
            matches.append((phrase in " ".join(text.split()).casefold(), order, entry))
    matches.sort(key=lambda row: (row[0], row[1]), reverse=True)
    return [entry for _, _, entry in matches[:limit]], len(matches)


def compact(value: object, length: int = SNIPPET_LENGTH) -> str:
    text = " ".join(str(value or "").split())
    return text[:length] + (" …" if len(text) > length else "")


def compact_entry(entry: dict) -> str:
    campaign = entry.get("campaign") or "uncategorized"
    return f"#{entry.get('id')} [{entry.get('verdict')}] {campaign}: {compact(entry.get('object'))}"


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


def _add_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="explog add", description="Append one ledger record")
    parser.add_argument("--verdict", choices=VERDICTS, required=True)
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
    parser.add_argument("query")
    parser.add_argument("--limit", type=int, default=DEFAULT_LIMIT)
    parser.add_argument("--json", action="store_true")
    return parser


def _validate_add(args: argparse.Namespace, entries: list[dict]) -> tuple[bool, dict]:
    running = args.verdict == "running"
    if running:
        if not all((args.claim_object.strip(), args.operation.strip(), args.decision.strip())):
            print("a running claim needs --object, --operation and --decision", file=sys.stderr)
            return False, {}
        if any((args.coverage, args.result, args.evidence, args.resolves)):
            print("a running claim cannot contain result fields", file=sys.stderr)
            return False, {}
        duplicate = next((
            entry for entry in current(entries)
            if normalized(entry.get("object")) == normalized(args.claim_object)
            and normalized(entry.get("operation")) == normalized(args.operation)
        ), None)
        if duplicate:
            print(f"operation already reserved by #{duplicate.get('id')}", file=sys.stderr)
            return False, {}
        return True, {
            "campaign": args.campaign.strip() or current_wake_id(),
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
    try:
        claim = entries_by_id(entries, [target_id])[0]
    except ValueError as exc:
        print(exc, file=sys.stderr)
        return False, {}
    active_ids = {entry.get("id") for entry in current(entries)}
    if claim.get("verdict") != "running":
        print("--resolves must name running claims", file=sys.stderr)
        return False, {}
    if target_id not in active_ids:
        print(f"claim already resolved: {target_id}", file=sys.stderr)
        return False, {}
    return True, {
        "campaign": claim.get("campaign") or current_wake_id(),
        "route": claim.get("route", ""),
        "object": claim.get("object", ""),
        "operation": claim.get("operation", ""),
        "decision": claim.get("decision", ""),
        "coverage": args.coverage.strip(),
        "result": args.result.strip(),
        "evidence": [value.strip() for value in args.evidence if value.strip()],
        "resolves": target_id,
    }


def add(args: argparse.Namespace) -> int:
    target, wake_id = write_log_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    lock_path = target if not sharded_mode() else SHARD_DIR / ".lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("a+", encoding="utf-8") as lock_file, locked(lock_file):
        bad: list[str] = []
        entries = read_log(bad)
        if bad:
            print("refusing to append while log records are unreadable", file=sys.stderr)
            return 2
        errors = ledger_errors(entries)
        if errors:
            print(f"refusing to append: {errors[0]}", file=sys.stderr)
            return 2
        valid, values = _validate_add(args, entries)
        if not valid:
            return 2
        if wake_id:
            prefix = f"{wake_id}:"
            sequences = [
                int(str(entry["id"]).removeprefix(prefix))
                for entry in entries
                if str(entry.get("id", "")).startswith(prefix)
                and str(entry["id"]).removeprefix(prefix).isdigit()
            ]
            entry_id: int | str = f"{wake_id}:{max(sequences, default=0) + 1}"
        else:
            numeric = [entry.get("id") for entry in entries if isinstance(entry.get("id"), int)]
            entry_id = max(numeric, default=0) + 1
        entry = {
            "id": entry_id,
            "created_at": dt.datetime.now(dt.UTC).isoformat(timespec="seconds"),
            "verdict": args.verdict,
            **{key: value for key, value in values.items() if value not in (None, "", [], {})},
            "log_path": _display_path(target),
        }
        with target.open("a", encoding="utf-8") as output:
            output.write(json.dumps(entry, ensure_ascii=False, separators=(",", ":")) + "\n")
            output.flush()
            os.fsync(output.fileno())
    print(compact_entry(entry))
    return 0


def _help() -> None:
    print(__doc__.strip())


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] in {"-h", "--help"}:
        _help()
        return 0
    try:
        command = argv[0]
        if command == "add":
            return add(_add_parser().parse_args(argv[1:]))
        entries = read_log()
        if command == "show":
            args = _show_parser().parse_args(argv[1:])
            selected = entries_by_id(entries, args.ids)
            if args.json:
                json.dump(selected, sys.stdout, ensure_ascii=False, indent=2)
                print()
            else:
                render_full(selected)
            return 0
        if command == "running":
            args = _running_parser().parse_args(argv[1:])
            selected = current(entries)
            if args.json:
                json.dump(selected, sys.stdout, ensure_ascii=False, indent=2)
                print()
            else:
                render_full(selected)
            return 0
        args = _query_parser().parse_args(argv)
        if args.limit < 1:
            raise ValueError("--limit must be positive")
        matches, total = search_entries(entries, args.query, args.limit)
        if args.json:
            json.dump(
                match_payload(matches, total, args.query), sys.stdout,
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
