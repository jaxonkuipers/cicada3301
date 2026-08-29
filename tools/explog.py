"""Direct access to the current append-only Cicada experiment log.

``explog QUERY`` returns compact matching records. ``explog show ID...`` opens
selected records, ``explog running`` lists current locks, and ``explog add``
appends a record. Retrieval is a transparent scan of the log itself.
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
from dataclasses import dataclass

try:
    import fcntl
except ImportError:  # pragma: no cover - Windows retains single-writer use
    fcntl = None

from lib.paths import ROOT

SHARD_DIR = ROOT / "research" / "explog"
LOG = SHARD_DIR

HANDLE = re.compile(r"^[a-z0-9][a-z0-9-]{0,95}:[1-9][0-9]*$")
TOKEN = re.compile(r"[^\W_]+", re.UNICODE)
VERDICTS = (
    "candidate", "running", "survey", "disproved", "abandoned",
    "inconclusive", "underpowered", "promising", "explained", "solved",
)
WORK_CLASSES = (
    "puzzle", "reconstruction", "measurement", "source", "provenance", "review",
)
OPERATIONAL_WORK_CLASSES = frozenset(("puzzle", "reconstruction", "measurement"))
DEFAULT_LIMIT = 100
SNIPPET_LENGTH = 260

OBJECT_ALIASES = {
    "R12.3:845145127-domain": (
        "845145127.com", "845145127 domain", "2012 prime dimensions domain",
    ),
    "GP:rune-table": ("gematria primus table", "rune table", "Testout.jpg"),
    "R14.6:onion6-form": (
        "onion 6 form", "onion6", "onion6 square submission form",
        "magic square submission form",
    ),
    "R14.6:solver-service": (
        "solver hidden service", "key.asc callback", "cgi-bin upload callback",
    ),
    "R14.7:onion7-delivery": (
        "onion 7 delivery", "onion7", "58 body pages", "ky2khlqdf7qdznac",
    ),
    "LP:rune-body": (
        "liber primus rune body", "12956 unsolved runes", "LP2 body", "LP2",
    ),
    "LP:page49-byte-block": (
        "page 49 byte block", "page49", "pages 49 51 payload",
        "256 byte interruption",
    ),
    "LP:page56-digest": (
        "page 56 digest", "page56", "deep web hash", "512 bit value",
    ),
}


def tokens(value: object) -> tuple[str, ...]:
    """Case-folded unique terms in their original order."""
    if not isinstance(value, str):
        value = json.dumps(value, ensure_ascii=False, sort_keys=True)
    return tuple(dict.fromkeys(TOKEN.findall(value.casefold())))


def normalized(value: object) -> str:
    return " ".join(tokens(value))


OBJECT_LOOKUP = {
    normalized(label): object_id
    for object_id, aliases in OBJECT_ALIASES.items()
    for label in (object_id, *aliases)
}


def canonical_object(value: str) -> str:
    value = str(value or "").strip()
    return OBJECT_LOOKUP.get(normalized(value), value)


def parse_entry_id(value: str):
    value = str(value).strip()
    if value.isdigit():
        return int(value)
    if HANDLE.fullmatch(value):
        return value
    raise argparse.ArgumentTypeError("entry id is an integer or wake-name:sequence")


@contextlib.contextmanager
def locked(file):
    """Serialize id allocation and append, flushing before unlock."""
    if fcntl is None:
        yield
        file.flush()
        os.fsync(file.fileno())
        return
    fcntl.flock(file, fcntl.LOCK_EX)
    try:
        yield
        file.flush()
        os.fsync(file.fileno())
    finally:
        fcntl.flock(file, fcntl.LOCK_UN)


def sharded_mode() -> bool:
    return LOG == SHARD_DIR


def log_paths() -> list:
    if not sharded_mode():
        return [LOG] if LOG.exists() else []
    return sorted(SHARD_DIR.glob("*.jsonl")) if SHARD_DIR.exists() else []


def entry_time(entry: dict) -> str:
    if entry.get("created_at"):
        return str(entry["created_at"])
    try:
        return dt.datetime.strptime(
            str(entry.get("ts") or ""), "%Y-%m-%d %H:%M",
        ).replace(tzinfo=dt.UTC).isoformat()
    except ValueError:
        return str(entry.get("ts") or "")


def read_log(bad: list | None = None) -> list[dict]:
    """Read wake shards as one chronological sequence."""
    rows = []
    serial = 0
    for path in log_paths():
        for line_number, line in enumerate(
            path.read_text(encoding="utf-8").splitlines(), 1,
        ):
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
            entry.setdefault("log_path", str(path.relative_to(ROOT))
                             if path.is_relative_to(ROOT) else str(path))
            rows.append((entry_time(entry), serial, entry))
            serial += 1
    rows.sort(key=lambda row: (row[0], row[1]))
    return [entry for _, _, entry in rows]


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


def write_log_path() -> tuple:
    if not sharded_mode():
        return LOG, ""
    wake_id = current_wake_id()
    return SHARD_DIR / f"{wake_id}.jsonl", wake_id


def arm_of(entry: dict) -> str:
    if entry.get("arm"):
        return str(entry["arm"])
    params = entry.get("params")
    return str(params.get("arm") or "") if isinstance(params, dict) else ""


def relation_ids(entry: dict) -> set[object]:
    related: set[object] = set()
    values = entry.get("resolves") or []
    if not isinstance(values, list):
        values = [values]
    related.update(values)
    params = entry.get("params")
    if isinstance(params, dict) and params.get("resolves") is not None:
        values = params["resolves"]
        if not isinstance(values, list):
            values = [values]
        related.update(values)
    terminal = set(VERDICTS) - {"running", "candidate", "survey"}
    if entry.get("verdict") in terminal and entry.get("review_of") is not None:
        related.add(entry["review_of"])
    return related


def current(entries: list[dict]) -> list[dict]:
    """Return current state while respecting arms and explicit resolutions."""
    groups: dict[tuple[object, object], list[tuple[int, dict]]] = {}
    for index, entry in enumerate(entries):
        groups.setdefault((entry.get("section"), entry.get("method")), []).append(
            (index, entry)
        )

    selected: list[tuple[int, dict]] = []
    for group in groups.values():
        unarmed = [(index, entry) for index, entry in group if not arm_of(entry)]
        armed: dict[str, tuple[int, dict]] = {}
        for index, entry in group:
            if arm := arm_of(entry):
                armed[arm] = (index, entry)
        latest_unarmed = unarmed[-1] if unarmed else None
        latest_armed_index = max((index for index, _ in armed.values()), default=-1)
        if latest_unarmed and latest_unarmed[0] > latest_armed_index:
            selected.append(latest_unarmed)
        elif armed:
            selected.extend(armed.values())
        elif latest_unarmed:
            selected.append(latest_unarmed)

    resolved = set().union(*(relation_ids(entry) for entry in entries)) if entries else set()
    return [
        entry for _, entry in sorted(selected)
        if entry.get("id") not in resolved
    ]


SEARCH_FIELDS = (
    ("method", 8), ("arm", 7), ("object", 7), ("operation", 7),
    ("coverage", 5), ("notes", 4), ("payoff", 3), ("prior", 2),
    ("params", 1), ("route", 1), ("section", 1), ("verdict", 1),
)


@dataclass(frozen=True)
class Match:
    entry: dict
    matched: tuple[str, ...]
    score: int
    field: str
    snippet: str
    order: int


def field_texts(entry: dict) -> dict[str, str]:
    fields = {}
    for name, _ in SEARCH_FIELDS:
        value = entry.get(name)
        if value in (None, "", [], {}):
            fields[name] = ""
        elif isinstance(value, str):
            fields[name] = value
        else:
            fields[name] = json.dumps(value, ensure_ascii=False, sort_keys=True)
    object_id = canonical_object(str(entry.get("object") or ""))
    if object_id in OBJECT_ALIASES:
        fields["object"] += " " + " ".join(OBJECT_ALIASES[object_id])
    return fields


def compact(value: str, length: int = SNIPPET_LENGTH) -> str:
    value = " ".join(value.split())
    return value[:length] + (" …" if len(value) > length else "")


def search_entries(
    entries: list[dict], query: str, limit: int = DEFAULT_LIMIT,
) -> tuple[list[Match], int]:
    """Rank direct record matches using visible lexical signals only."""
    query_terms = tokens(query)
    if not query_terms:
        raise ValueError("query contains no searchable terms")
    phrase = normalized(query)
    matches = []
    for order, entry in enumerate(entries):
        fields = field_texts(entry)
        field_tokens = {name: set(tokens(text)) for name, text in fields.items()}
        matched = tuple(
            term for term in query_terms
            if any(term in terms for terms in field_tokens.values())
        )
        if not matched:
            continue
        best_field = max(
            SEARCH_FIELDS,
            key=lambda item: (
                len(set(matched) & field_tokens[item[0]]) * item[1], item[1],
            ),
        )[0]
        score = sum(
            max(
                (weight for name, weight in SEARCH_FIELDS
                 if term in field_tokens[name]),
                default=0,
            )
            for term in matched
        )
        exact_fields = [
            name for name, weight in SEARCH_FIELDS
            if phrase and phrase in normalized(fields[name])
        ]
        if exact_fields:
            score += 40 + max(dict(SEARCH_FIELDS)[name] for name in exact_fields)
            best_field = exact_fields[0]
        matches.append(Match(
            entry, matched, score, best_field,
            compact(fields[best_field]), order,
        ))
    matches.sort(key=lambda match: (-match.score, -len(match.matched), -match.order))
    return matches[:limit], len(matches)


def compact_entry(entry: dict) -> str:
    arm = f"/{arm_of(entry)}" if arm_of(entry) else ""
    return (
        f"#{entry.get('id')} [{entry.get('verdict')}] "
        f"{entry.get('section')} {entry.get('method')}{arm}"
    )


def render_matches(matches: list[Match], total: int) -> None:
    if not matches:
        print("no matching Explog entries")
        return
    for match in matches:
        print(compact_entry(match.entry))
        print(f"    matched: {', '.join(match.matched)}")
        print(f"    {match.field}: {match.snippet}")
    print(f"\n{len(matches)} of {total} matching entries", file=sys.stderr)


def match_payload(matches: list[Match], total: int, query: str) -> dict:
    return {
        "query": query,
        "hits": total,
        "shown": len(matches),
        "results": [
            {
                "id": match.entry.get("id"),
                "section": match.entry.get("section"),
                "verdict": match.entry.get("verdict"),
                "method": match.entry.get("method"),
                "arm": arm_of(match.entry) or None,
                "matched": list(match.matched),
                "field": match.field,
                "snippet": match.snippet,
            }
            for match in matches
        ],
    }


def entries_by_id(entries: list[dict], ids: list[object]) -> list[dict]:
    lookup = {entry.get("id"): entry for entry in entries}
    missing = [entry_id for entry_id in ids if entry_id not in lookup]
    if missing:
        raise ValueError("unknown Explog ids: " + ", ".join(map(str, missing)))
    return [lookup[entry_id] for entry_id in ids]


def render_full(entries: list[dict]) -> None:
    if not entries:
        print("no entries")
        return
    for entry in entries:
        print(compact_entry(entry))
        for key, value in entry.items():
            if key in {"id", "section", "verdict", "method"} or value in (None, "", [], {}):
                continue
            if isinstance(value, (dict, list)):
                value = json.dumps(value, ensure_ascii=False, sort_keys=True)
            print(f"    {key}: {value}")


def known_sections() -> tuple[str, ...]:
    from lib import corpus
    return ("all", *(section.id for section in corpus.load().sections))


def normalize_source_family(value: object) -> str:
    if not isinstance(value, str):
        return ""
    value = value.strip().casefold().removesuffix(".git").rstrip("/")
    for prefix in ("https://github.com/", "http://github.com/", "git@github.com:"):
        if value.startswith(prefix):
            return value[len(prefix):]
    return value


def source_family_of(entry: dict) -> str:
    value = entry.get("source_family")
    if not value and isinstance(entry.get("params"), dict):
        value = entry["params"].get("source_repo")
    return normalize_source_family(value)


def work_class_of(entry: dict) -> str:
    value = str(entry.get("work_class") or "").casefold()
    if value in WORK_CLASSES:
        return value
    if entry.get("review_of") is not None:
        return "review"
    if source_family_of(entry) or entry.get("verdict") == "survey":
        return "source"
    method = str(entry.get("method") or "").casefold()
    if method.endswith("-review") or "-review-" in method:
        return "review"
    if method.startswith("external-") or any(
        marker in method for marker in (
            "source-recovery", "source-family", "archive-audit", "common-crawl",
            "wayback", "ghtorrent",
        )
    ):
        return "source"
    if "provenance" in method or "custody" in method:
        return "provenance"
    return "puzzle"


def validate_add(args: argparse.Namespace) -> tuple[bool, dict]:
    if args.section not in known_sections():
        print(f"unknown section {args.section!r}", file=sys.stderr)
        return False, {}
    source_family = normalize_source_family(args.source_family)
    work_class = (
        args.work_class
        or ("review" if args.review_of is not None else "")
        or ("source" if source_family or args.verdict == "survey" else "puzzle")
    )
    claim_object = canonical_object(args.claim_object)
    if args.verdict in {"running", "candidate"} and not all(
        (claim_object, args.operation, args.decision)
    ):
        print(
            f"a {args.verdict} claim needs --object, --operation and --decision",
            file=sys.stderr,
        )
        return False, {}
    if args.verdict == "running" and any((
        args.payoff, args.prior, args.params, args.coverage, args.notes,
        args.review_of,
    )):
        print("a running claim contains only its object, operation and decision", file=sys.stderr)
        return False, {}
    if args.verdict in {"running", "candidate"} and (
        args.method.startswith("external-") or source_family
        or args.source_parent is not None or work_class not in OPERATIONAL_WORK_CLASSES
    ):
        print("a claim must reserve a Cicada object and operation", file=sys.stderr)
        return False, {}
    if args.verdict == "candidate" and not args.payoff:
        print("a candidate needs --payoff", file=sys.stderr)
        return False, {}
    if args.supports is not None and not (source_family and args.verdict == "survey"):
        print("--supports belongs on a source-family survey", file=sys.stderr)
        return False, {}
    if args.verdict == "solved":
        from lib.corpus import UNSOLVED_SECTIONS
        if args.section not in UNSOLVED_SECTIONS:
            print("--verdict solved names one unsolved section", file=sys.stderr)
            return False, {}
    params = args.params
    if params:
        try:
            params = json.loads(params)
        except json.JSONDecodeError:
            pass
    return True, {
        "route": args.route,
        "source_family": source_family,
        "source_parent": args.source_parent,
        "supports": args.supports,
        "resolves": list(args.resolves or []),
        "object": claim_object,
        "operation": args.operation,
        "decision": args.decision,
        "work_class": work_class,
        "payoff": args.payoff,
        "params": params,
    }


def add(args: argparse.Namespace) -> int:
    valid, values = validate_add(args)
    if not valid:
        return 2
    target_log, wake_id = write_log_path()
    target_log.parent.mkdir(parents=True, exist_ok=True)
    with open(target_log, "a", encoding="utf-8") as file, locked(file):
        bad: list[str] = []
        entries = read_log(bad)
        if bad:
            print("refusing to append while log records are unreadable", file=sys.stderr)
            return 2
        existing = {entry.get("id") for entry in entries}
        for label in ("review_of", "supports"):
            value = getattr(args, label)
            if value is not None and value not in existing:
                print(f"--{label.replace('_', '-')} names missing entry #{value}", file=sys.stderr)
                return 2
        missing = [entry_id for entry_id in values["resolves"] if entry_id not in existing]
        if missing:
            print(
                "--resolves names missing entries: " + ", ".join(map(str, missing)),
                file=sys.stderr,
            )
            return 2
        if values["resolves"] and args.verdict in {"running", "candidate"}:
            print("--resolves belongs on a result", file=sys.stderr)
            return 2
        if values["source_family"] and args.verdict == "survey":
            if args.supports is None:
                print("a source-family survey needs --supports", file=sys.stderr)
                return 2
            target = next(entry for entry in entries if entry.get("id") == args.supports)
            if target.get("verdict") not in {"running", "candidate"}:
                print("--supports must name a running or candidate claim", file=sys.stderr)
                return 2
            values["route"] = values["route"] or target.get("route", "")
        if args.verdict != "running":
            claims = [
                entry for entry in current(entries)
                if entry.get("verdict") == "running"
                and entry.get("section") == args.section
                and entry.get("method") == args.method
                and (not arm_of(entry) or arm_of(entry) == args.arm)
            ]
            if claims:
                claim = claims[-1]
                if claim.get("id") not in values["resolves"]:
                    values["resolves"].append(claim.get("id"))
                inherited = (
                    "route", "object", "operation", "decision", "source_family",
                    "source_parent",
                )
                for name in inherited:
                    values[name] = values[name] or claim.get(name, "")
                values["work_class"] = claim.get("work_class") or work_class_of(claim)

        now = dt.datetime.now(dt.UTC)
        if wake_id:
            prefix = f"{wake_id}:"
            sequences = [
                int(str(entry["id"]).removeprefix(prefix))
                for entry in entries
                if str(entry.get("id", "")).startswith(prefix)
                and str(entry["id"]).removeprefix(prefix).isdigit()
            ]
            entry_id = f"{wake_id}:{max(sequences, default=0) + 1}"
        else:
            numeric = [entry.get("id") for entry in entries if isinstance(entry.get("id"), int)]
            entry_id = max(numeric, default=0) + 1

        entry = {
            "id": entry_id,
            "ts": now.strftime("%Y-%m-%d %H:%M"),
            "created_at": now.isoformat(timespec="microseconds"),
            "section": args.section,
            "method": args.method,
            "arm": args.arm,
            "review_of": args.review_of,
            "resolves": values["resolves"],
            "route": values["route"],
            "object": values["object"],
            "operation": values["operation"],
            "decision": values["decision"],
            "work_class": values["work_class"],
            "source_family": values["source_family"],
            "source_parent": values["source_parent"],
            "supports": values["supports"],
            "payoff": values["payoff"],
            "params": values["params"],
            "prior": args.prior,
            "coverage": args.coverage,
            "verdict": args.verdict,
            "notes": args.notes,
        }
        if wake_id:
            entry["log_path"] = str(target_log.relative_to(ROOT))
        file.write(json.dumps(entry, ensure_ascii=False) + "\n")
    try:
        destination = target_log.relative_to(ROOT)
    except ValueError:
        destination = target_log
    print(f"logged #{entry_id} ({args.verdict}) to {destination}")
    return 0


def add_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python3 -m tools.explog add")
    parser.add_argument("--section", required=True)
    parser.add_argument("--method", required=True)
    parser.add_argument("--arm", default="")
    parser.add_argument("--route", default="")
    parser.add_argument("--object", dest="claim_object", default="")
    parser.add_argument("--operation", default="")
    parser.add_argument("--decision", default="")
    parser.add_argument("--work-class", choices=WORK_CLASSES, default="")
    parser.add_argument("--source-family", default="")
    parser.add_argument("--source-parent", type=parse_entry_id)
    parser.add_argument("--supports", type=parse_entry_id)
    parser.add_argument("--payoff", default="")
    parser.add_argument("--params", default="")
    parser.add_argument("--prior", default="")
    parser.add_argument("--review-of", type=parse_entry_id)
    parser.add_argument("--resolves", type=parse_entry_id, action="append")
    parser.add_argument("--coverage", default="")
    parser.add_argument("--verdict", required=True, choices=VERDICTS)
    parser.add_argument("--notes", default="")
    return parser


def query_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python3 -m tools.explog",
        description="Search Explog records. Use `explog show ID...` for full entries.",
    )
    parser.add_argument("query")
    parser.add_argument("--limit", type=int, default=DEFAULT_LIMIT)
    parser.add_argument("--json", action="store_true")
    return parser


def show_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python3 -m tools.explog show")
    parser.add_argument("ids", nargs="+", type=parse_entry_id)
    parser.add_argument("--json", action="store_true")
    return parser


def running_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python3 -m tools.explog running")
    parser.add_argument("--json", action="store_true")
    return parser


def print_help() -> None:
    print(
        "usage:\n"
        "  python3 -m tools.explog QUERY [--limit N] [--json]\n"
        "  python3 -m tools.explog show ID [ID ...] [--json]\n"
        "  python3 -m tools.explog running [--json]\n"
        "  python3 -m tools.explog add ...\n\n"
        "Search first, then open only the relevant record ids with show."
    )


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv in (["-h"], ["--help"]):
        print_help()
        return 0
    try:
        command = argv[0]
        if command == "add":
            return add(add_parser().parse_args(argv[1:]))
        entries = read_log()
        if command == "show":
            args = show_parser().parse_args(argv[1:])
            selected = entries_by_id(entries, args.ids)
            if args.json:
                json.dump(selected, sys.stdout, ensure_ascii=False, indent=1)
                print()
            else:
                render_full(selected)
            return 0
        if command == "running":
            args = running_parser().parse_args(argv[1:])
            selected = [entry for entry in current(entries) if entry.get("verdict") == "running"]
            if args.json:
                json.dump(selected, sys.stdout, ensure_ascii=False, indent=1)
                print()
            else:
                render_full(selected)
            return 0
        args = query_parser().parse_args(argv)
        if args.limit < 1:
            raise ValueError("--limit must be positive")
        matches, total = search_entries(entries, args.query, args.limit)
        if args.json:
            json.dump(
                match_payload(matches, total, args.query), sys.stdout,
                ensure_ascii=False, indent=1,
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
