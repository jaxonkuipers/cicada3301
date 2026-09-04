"""Append-only experiment ledger shared by concurrent solver wakes.

The ledger is a directory of per-wake JSONL shards read together as one
chronological record. Running records reserve an object and exact operation;
result records close named reservations with explicit coverage. This module is
the data contract -- reading, validation predicates and append primitives. The
locked read-validate-append transaction is sequenced by
`solver.cli.explog.add()`; write through that command, not these primitives.
"""

from __future__ import annotations

import contextlib
import csv
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

try:
    import fcntl
except ImportError:  # pragma: no cover - Windows retains single-writer use
    fcntl = None

from solver.paths import ROOT

VERDICTS = ("running", "negative", "positive", "blocked")
INHERITED_FIELDS = ("campaign", "route", "object", "operation", "decision")
HANDLE = re.compile(r"^[a-z0-9][a-z0-9-]{0,95}:[1-9][0-9]*$")
TOKEN = re.compile(r"[^\W_]+", re.UNICODE)
DEFAULT_LIMIT = 100


def tokens(value: object) -> tuple[str, ...]:
    """Return unique case-folded words in original order."""
    if not isinstance(value, str):
        value = json.dumps(value, ensure_ascii=False, sort_keys=True)
    return tuple(dict.fromkeys(TOKEN.findall(value.casefold())))


def normalized(value: object) -> str:
    return " ".join(tokens(value))


def route_ids(root: Path = ROOT) -> frozenset[str]:
    """Load the canonical route keys used by claims."""
    path = root / "corpus" / "route.csv"
    try:
        with path.open(encoding="utf-8", newline="") as source:
            rows = list(csv.DictReader(source))
    except OSError as exc:
        raise ValueError(f"cannot read corpus/route.csv: {exc}") from exc
    if not rows or "route" not in rows[0]:
        raise ValueError("corpus/route.csv has no route column or rows")
    routes = frozenset(
        route for row in rows if (route := str(row.get("route", "")).strip())
    )
    if not routes:
        raise ValueError("corpus/route.csv contains no route ids")
    return routes


def validate_route(
    value: str, known_routes: frozenset[str] | None = None, *, root: Path = ROOT,
) -> str | None:
    route = value.strip()
    if not route:
        return "a running claim needs --route"
    if known_routes is None:
        try:
            known_routes = route_ids(root)
        except ValueError as exc:
            return str(exc)
    if route not in known_routes:
        return f"unknown route {route}; choose an id from corpus/route.csv"
    return None


def validated_evidence(
    values: list[str], *, root: Path = ROOT,
) -> tuple[list[str], str | None]:
    """Return canonical repository-relative paths for existing evidence files."""
    paths: list[str] = []
    resolved_root = root.resolve()
    for value in values:
        value = value.strip()
        if not value:
            return [], "--evidence cannot be empty"
        supplied = Path(value)
        candidate = supplied if supplied.is_absolute() else root / supplied
        resolved = candidate.resolve()
        try:
            relative = resolved.relative_to(resolved_root)
        except ValueError:
            return [], f"evidence path leaves the repository: {value}"
        if not resolved.is_file():
            return [], f"evidence is not an existing regular file: {value}"
        paths.append(relative.as_posix())
    return paths, None


def entry_time(entry: dict) -> str:
    return str(entry.get("created_at") or entry.get("ts") or "")


@dataclass(frozen=True)
class Ledger:
    """One ledger, anchored at a repository root.

    The root anchors route and evidence validation and the display form of
    shard paths; the derived shard directory -- the committed research/explog
    -- holds one JSONL file per wake plus the append lock. Tests construct
    their own against a temporary tree; everything else uses `DEFAULT`.
    """

    root: Path

    @property
    def shard_dir(self) -> Path:
        return self.root / "research" / "explog"

    def paths(self) -> list[Path]:
        """All wake shards, in stable name order."""
        if not self.shard_dir.exists():
            return []
        return sorted(self.shard_dir.glob("*.jsonl"))

    def shard(self, wake_id: str) -> Path:
        return self.shard_dir / f"{wake_id}.jsonl"

    @property
    def lock_path(self) -> Path:
        return self.shard_dir / ".lock"

    def display(self, path: Path) -> str:
        try:
            return str(path.relative_to(self.root))
        except ValueError:
            return str(path)

    def read(self, bad: list[str] | None = None) -> list[dict]:
        """Read all wake shards as one chronological record."""
        rows: list[tuple[str, int, dict]] = []
        serial = 0
        for path in self.paths():
            display_path = self.display(path)
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
                        f"warning: {location} is a JSON {type(entry).__name__}, "
                        "expected object",
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


DEFAULT = Ledger(root=ROOT)


def current_wake_id(runner=subprocess.run, *, root: Path = ROOT) -> str:
    supplied = os.environ.get("CICADA_WAKE_ID", "").strip().casefold()
    if supplied:
        if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,95}", supplied):
            raise ValueError(
                "invalid CICADA_WAKE_ID; use 1-96 lowercase letters, digits or hyphens"
            )
        return supplied
    try:
        result = runner(
            ["git", "branch", "--show-current"], cwd=root, check=True,
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


def next_id(entries: list[dict], wake_id: str) -> str:
    """The next sequential `wake:sequence` handle for `wake_id`'s shard."""
    prefix = f"{wake_id}:"
    sequences = [
        int(str(entry["id"]).removeprefix(prefix))
        for entry in entries
        if str(entry.get("id", "")).startswith(prefix)
        and str(entry["id"]).removeprefix(prefix).isdigit()
    ]
    return f"{wake_id}:{max(sequences, default=0) + 1}"


def append_line(target: Path, entry: dict) -> None:
    """Durably append one record to a shard.

    A primitive, not the transaction: the caller must hold `locked` on the
    ledger's lock file and have validated the grown record set the way
    `solver.cli.explog.add()` does, or one malformed row blocks every wake's
    next append.
    """
    with target.open("a", encoding="utf-8") as output:
        output.write(json.dumps(entry, ensure_ascii=False, separators=(",", ":")) + "\n")
        output.flush()
        os.fsync(output.fileno())


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
    root: Path = ROOT,
) -> list[str]:
    """Report mutable route/evidence references without disabling Explog."""
    warnings: list[str] = []
    routes_available = True
    if known_routes is None:
        try:
            known_routes = route_ids(root)
        except ValueError as exc:
            warnings.append(str(exc))
            known_routes = frozenset()
            routes_available = False
    for entry in entries:
        entry_id = entry.get("id")
        if routes_available:
            route_error = validate_route(
                str(entry.get("route", "")), known_routes, root=root,
            )
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
        canonical, evidence_error = validated_evidence(evidence, root=root)
        if evidence_error:
            warnings.append(f"result {entry_id} has stale evidence: {evidence_error}")
        elif canonical != evidence:
            warnings.append(f"result {entry_id} evidence paths are not canonical")
    return warnings


def reservation_key(claim_object: object, operation: object) -> tuple[str, str]:
    """The collision key under which a running claim locks its operation."""
    return (normalized(claim_object), normalized(operation))


def find_active_duplicate(
    entries: list[dict], claim_object: object, operation: object,
) -> dict | None:
    """The active reservation already holding (object, operation), if any."""
    key = reservation_key(claim_object, operation)
    for entry in current(entries):
        if reservation_key(entry.get("object"), entry.get("operation")) == key:
            return entry
    return None


def active_duplicate_errors(entries: list[dict]) -> list[str]:
    """Return duplicate operation reservations remaining after all closures."""
    errors: list[str] = []
    reservations: dict[tuple[str, str], int | str] = {}
    for entry in current(entries):
        key = reservation_key(entry.get("object"), entry.get("operation"))
        previous = reservations.get(key)
        if previous is not None:
            errors.append(
                f"running claim {entry.get('id')} duplicates active operation {previous}"
            )
        else:
            reservations[key] = entry.get("id")
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
