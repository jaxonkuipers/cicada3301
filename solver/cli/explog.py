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
import csv
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


def route_ids() -> frozenset[str]:
    """Load the canonical route keys used by claims."""
    path = ROOT / "corpus" / "route.csv"
    try:
        with path.open(encoding="utf-8", newline="") as source:
            rows = list(csv.DictReader(source))
    except OSError as exc:
        raise ValueError(f"cannot read corpus/route.csv: {exc}") from exc
    if not rows or "route" not in (rows[0].keys() if rows else ()):
        raise ValueError("corpus/route.csv has no route column or rows")
    routes = frozenset(str(row.get("route", "")).strip() for row in rows)
    routes = frozenset(route for route in routes if route)
    if not routes:
        raise ValueError("corpus/route.csv contains no route ids")
    return routes


def validate_route(
    value: str, known_routes: frozenset[str] | None = None,
) -> str | None:
    route = value.strip()
    if not route:
        return "a running claim needs --route"
    if known_routes is None:
        try:
            known_routes = route_ids()
        except ValueError as exc:
            return str(exc)
    if route not in known_routes:
        return f"unknown route {route}; choose an id from corpus/route.csv"
    return None


def validated_evidence(values: list[str]) -> tuple[list[str], str | None]:
    """Return canonical repository-relative paths for existing evidence files."""
    paths: list[str] = []
    root = ROOT.resolve()
    for value in values:
        value = value.strip()
        if not value:
            return [], "--evidence cannot be empty"
        supplied = Path(value)
        candidate = supplied if supplied.is_absolute() else ROOT / supplied
        resolved = candidate.resolve()
        try:
            relative = resolved.relative_to(root)
        except ValueError:
            return [], f"evidence path leaves the repository: {value}"
        if not resolved.is_file():
            return [], f"evidence is not an existing regular file: {value}"
        paths.append(relative.as_posix())
    return paths, None


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
        display_path = _display_path(path)
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError as exc:
            print(
                f"warning: {display_path} is not valid UTF-8 at byte {exc.start}",
                file=sys.stderr,
            )
            if bad is not None:
                bad.append(display_path)
            continue
        except OSError as exc:
            print(f"warning: cannot read {display_path}: {exc}", file=sys.stderr)
            if bad is not None:
                bad.append(display_path)
            continue
        for line_number, line in enumerate(text.splitlines(), 1):
            if not line.strip():
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError as exc:
                location = f"{display_path}:{line_number}"
                print(f"warning: {location} is not valid JSON: {exc}", file=sys.stderr)
                if bad is not None:
                    bad.append(location)
                continue
            if not isinstance(entry, dict):
                location = f"{display_path}:{line_number}"
                print(
                    f"warning: {location} is a JSON {type(entry).__name__}, expected object",
                    file=sys.stderr,
                )
                if bad is not None:
                    bad.append(location)
                continue
            if "log_path" not in entry:
                entry["log_path"] = display_path
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
        if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,95}", supplied):
            raise ValueError(
                "invalid CICADA_WAKE_ID; use 1-96 lowercase letters, digits or hyphens"
            )
        return supplied
    try:
        result = runner(
            ["git", "branch", "--show-current"], cwd=ROOT, check=True,
            text=True, capture_output=True,
        )
        branch = result.stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        branch = ""
    if branch.startswith("wake/"):
        wake_id = re.sub(
            r"[^a-z0-9-]+", "-", branch.removeprefix("wake/").casefold(),
        ).strip("-")[:96]
        if wake_id:
            return wake_id
    print(
        "warning: using fallback Explog wake id 'local'; set CICADA_WAKE_ID "
        "or use a managed wake worktree",
        file=sys.stderr,
    )
    return "local"


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
        if entry.get("verdict") not in VERDICTS[1:]:
            continue
        target = entry.get("resolves")
        if isinstance(target, (int, str)) and not isinstance(target, bool) \
                and target not in (None, ""):
            resolved.add(target)
    return resolved


def current(entries: list[dict]) -> list[dict]:
    """Return unresolved running locks."""
    resolved = resolved_ids(entries)
    return [
        entry for entry in entries
        if entry.get("verdict") == "running" and entry.get("id") not in resolved
    ]


def lifecycle_errors(entries: list[dict]) -> list[str]:
    """Return immutable record-shape and resolution violations."""
    errors: list[str] = []
    seen: dict[int | str, dict] = {}
    for entry in entries:
        entry_id = entry.get("id")
        valid_id = (
            isinstance(entry_id, int)
            and not isinstance(entry_id, bool)
            and entry_id > 0
        ) or (
            isinstance(entry_id, str)
            and HANDLE.fullmatch(entry_id) is not None
        )
        if not valid_id:
            errors.append(f"invalid Explog id {entry_id!r}")
            continue
        if entry_id in seen:
            errors.append(f"duplicate Explog id {entry_id}")
            continue
        verdict = entry.get("verdict")
        if verdict not in VERDICTS:
            errors.append(f"record {entry_id} has invalid verdict {verdict!r}")
        elif verdict == "running":
            missing = [
                field for field in ("route", "object", "operation", "decision")
                if not str(entry.get(field, "")).strip()
            ]
            if missing:
                errors.append(
                    f"running claim {entry_id} lacks " + ", ".join(missing)
                )
            result_fields = [
                field for field in ("coverage", "result", "evidence", "resolves")
                if entry.get(field) not in (None, "", [], {})
            ]
            if result_fields:
                errors.append(
                    f"running claim {entry_id} contains result fields: "
                    + ", ".join(result_fields)
                )
        else:
            missing = [
                field for field in ("coverage", "result")
                if not str(entry.get(field, "")).strip()
            ]
            if missing:
                errors.append(
                    f"result {entry_id} lacks " + ", ".join(missing)
                )
            evidence = entry.get("evidence")
            if verdict in {"negative", "positive"} \
                    and (not isinstance(evidence, list) or not evidence):
                errors.append(f"result {entry_id} lacks evidence")
            elif evidence not in (None, []) and not isinstance(evidence, list):
                errors.append(f"result {entry_id} evidence must be a list of paths")
            elif isinstance(evidence, list) and not all(
                isinstance(path, str) and path for path in evidence
            ):
                errors.append(f"result {entry_id} evidence must be a list of paths")
        seen[entry_id] = entry

    closures: dict[int | str, int | str] = {}
    for entry in entries:
        if entry.get("verdict") == "running":
            continue
        entry_id = entry.get("id")
        target_id = entry.get("resolves")
        if not isinstance(target_id, (int, str)) or isinstance(target_id, bool) \
                or target_id == "":
            errors.append(f"result {entry_id} must resolve exactly one running ID")
        elif target_id not in seen:
            errors.append(f"result {entry_id} has an unknown reference to {target_id}")
        else:
            target = seen[target_id]
            if target.get("verdict") != "running":
                errors.append(f"result {entry_id} resolves non-running record {target_id}")
            else:
                previous = closures.get(target_id)
                if previous is not None:
                    errors.append(
                        f"result {entry_id} resolves already closed claim {target_id} "
                        f"(also resolved by {previous})"
                    )
                else:
                    closures[target_id] = entry_id
            mismatched = [
                field for field in INHERITED_FIELDS
                if entry.get(field, "") != target.get(field, "")
            ]
            if mismatched:
                errors.append(
                    f"result {entry_id} differs from claim {target_id} in "
                    + ", ".join(mismatched)
                )
    return errors


def reference_warnings(
    entries: list[dict], *,
    known_routes: frozenset[str] | None = None,
    known_evidence: frozenset[str] | None = None,
) -> list[str]:
    """Report mutable route/evidence references without disabling Explog."""
    warnings: list[str] = []
    routes_available = True
    if known_routes is None:
        try:
            known_routes = route_ids()
        except ValueError as exc:
            warnings.append(str(exc))
            known_routes = frozenset()
            routes_available = False
    for entry in entries:
        entry_id = entry.get("id")
        if routes_available:
            route_error = validate_route(str(entry.get("route", "")), known_routes)
            if route_error:
                warnings.append(f"record {entry_id} has stale route: {route_error}")
        evidence = entry.get("evidence")
        if not isinstance(evidence, list) or not evidence:
            continue
        if known_evidence is not None:
            missing = [path for path in evidence if path not in known_evidence]
            if missing:
                warnings.append(
                    f"result {entry_id} has evidence absent from the snapshot: "
                    + ", ".join(map(str, missing))
                )
            continue
        if not all(isinstance(path, str) for path in evidence):
            continue
        canonical, evidence_error = validated_evidence(evidence)
        if evidence_error:
            warnings.append(f"result {entry_id} has stale evidence: {evidence_error}")
        elif canonical != evidence:
            warnings.append(f"result {entry_id} evidence paths are not canonical")
    return warnings


def active_duplicate_errors(entries: list[dict]) -> list[str]:
    """Return duplicate operation reservations remaining after all closures."""
    errors: list[str] = []
    reservations: dict[tuple[str, str], int | str] = {}
    for entry in current(entries):
        key = (normalized(entry.get("object")), normalized(entry.get("operation")))
        previous = reservations.get(key)
        if previous is not None:
            errors.append(
                f"running claim {entry.get('id')} duplicates active operation {previous}"
            )
        else:
            reservations[key] = entry.get("id")
    return errors


def ledger_errors(entries: list[dict]) -> list[str]:
    """Return hard lifecycle errors; reservation collisions are warnings."""
    return lifecycle_errors(entries)


def warn_active_duplicates(entries: list[dict]) -> None:
    for warning in active_duplicate_errors(entries):
        print(f"warning: {warning}", file=sys.stderr)


def warn_reference_drift(entries: list[dict]) -> None:
    for warning in reference_warnings(entries):
        print(f"warning: {warning}", file=sys.stderr)


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
    parser.add_argument("query", nargs="+")
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
        route_error = validate_route(args.route)
        if route_error:
            print(route_error, file=sys.stderr)
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
    if args.verdict != "blocked" and not args.evidence:
        print("a result needs at least one --evidence path", file=sys.stderr)
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
    evidence: list[str] = []
    if args.evidence:
        evidence, evidence_error = validated_evidence(args.evidence)
        if evidence_error:
            print(evidence_error, file=sys.stderr)
            return False, {}
    values = {
        "campaign": claim.get("campaign") or current_wake_id(),
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
        errors = lifecycle_errors(entries)
        if errors:
            print(f"refusing to append: {errors[0]}", file=sys.stderr)
            return 2
        warn_reference_drift(entries)
        warn_active_duplicates(entries)
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


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] in {"-h", "--help"}:
        _help()
        return 0
    try:
        command = argv[0]
        if command == "add":
            return add(_add_parser().parse_args(argv[1:]))
        typo = _likely_command_typo(command)
        if typo:
            raise ValueError(f"unknown command {command!r}; did you mean {typo!r}?")
        bad: list[str] = []
        entries = read_log(bad)
        if bad:
            print(
                "warning: some Explog records were unreadable; showing readable records",
                file=sys.stderr,
            )
        for error in lifecycle_errors(entries):
            print(f"warning: invalid Explog ledger: {error}", file=sys.stderr)
        warn_reference_drift(entries)
        warn_active_duplicates(entries)
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
        query = " ".join(args.query)
        matches, total = search_entries(entries, query, args.limit)
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
