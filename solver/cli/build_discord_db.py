"""Rebuild ``discord.db`` from the preserved local Git snapshot.

The raw DiscordChatExporter files remain in commit ``71b0eba`` and are read
through Git object storage. The builder performs no network access and writes
no raw export into the worktree.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sqlite3
import sys
import tempfile
from collections import Counter
from collections.abc import Iterable, Iterator, Sequence
from contextlib import closing
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path, PurePosixPath

from solver import runes
from solver.cli._git_source import SOURCE_COMMIT, GitSource
from solver.paths import DISCORD_DB

HEADER = re.compile(
    r"^\[([0-9]{1,2}/[0-9]{1,2}/[0-9]{4}) ([0-9]{1,2}:[0-9]{2} [AP]M)\] (.+)$"
)
BRACE_BLOCK = re.compile(r"^\{(Embed|Attachments|Reactions|Stickers)\}$")
TIMESTAMP = "%m/%d/%Y %I:%M %p"
PINNED = " (pinned)"
MIN_CANON = runes.MIN_INDEXED
MAX_RAW = 400

EXPECTED_EXPORTS = 13
EXPECTED_COUNTS = {"messages": 109_917, "runes": 7_755, "provenance": 13}
EXPECTED_LOGICAL_SHA256 = {
    "messages": "de1d59041a1b1f18e166e09c4ecdd66bb41855cbd5cf5b6f9765c26c6748f1d8",
    "runes": "63e7c36f5788e6a670421e8411d72880932e03610a2ddfd68d1612d86744af4d",
    "provenance": "68b6ce19fc44e04b780065f9807adfae01c0c10db46120152c5260d92095ed5c",
}

SCHEMA = """
PRAGMA page_size = 4096;
PRAGMA journal_mode = WAL;

CREATE TABLE messages (
    id           INTEGER PRIMARY KEY,
    channel      TEXT NOT NULL,
    channel_name TEXT NOT NULL,
    ts           TEXT NOT NULL,
    author       TEXT NOT NULL,
    pinned       INTEGER NOT NULL DEFAULT 0,
    body         TEXT NOT NULL,
    extra        TEXT NOT NULL,
    seq          INTEGER NOT NULL,
    line         INTEGER NOT NULL
);
CREATE INDEX msg_channel_seq ON messages(channel, seq);
CREATE INDEX msg_author ON messages(author);
CREATE INDEX msg_ts ON messages(ts);

CREATE VIRTUAL TABLE msg_fts USING fts5(body, extra, tokenize='unicode61');

CREATE TABLE runes (
    id       INTEGER PRIMARY KEY,
    msg_id   INTEGER NOT NULL REFERENCES messages(id),
    notation TEXT NOT NULL,
    raw      TEXT NOT NULL,
    canon    TEXT NOT NULL,
    n        INTEGER NOT NULL
);
CREATE INDEX runes_msg ON runes(msg_id);
CREATE VIRTUAL TABLE rune_fts USING fts5(canon, tokenize='trigram');

CREATE TABLE provenance (
    file   TEXT PRIMARY KEY,
    bytes  INTEGER NOT NULL,
    sha256 TEXT NOT NULL
);
"""

LOGICAL_TABLES = {
    "messages": "id,channel,channel_name,ts,author,pinned,body,extra,seq,line",
    "runes": "id,msg_id,notation,raw,canon,n",
    "provenance": "file,bytes,sha256",
}

EXPECTED_FTS_SQL = {
    "msg_fts": "CREATE VIRTUAL TABLE msg_fts USING fts5(body, extra, tokenize='unicode61')",
    "rune_fts": "CREATE VIRTUAL TABLE rune_fts USING fts5(canon, tokenize='trigram')",
}


@dataclass
class Message:
    channel: str
    channel_name: str
    ts: str
    author: str
    pinned: bool
    seq: int
    line: int
    body: list[str] = field(default_factory=list)
    extra: list[str] = field(default_factory=list)


def channel_name_of(lines: Sequence[str], default: str) -> str:
    for line in lines[:6]:
        if line.startswith("Channel:"):
            return line.split(":", 1)[1].strip()
    return default


def parse_export(path: str, data: bytes) -> Iterator[Message]:
    """Parse one strict UTF-8 DiscordChatExporter text export."""
    channel = PurePosixPath(path).stem
    lines = (
        data.decode("utf-8")
        .replace("\r\n", "\n")
        .replace("\r", "\n")
        .split("\n")
    )
    channel_name = channel_name_of(lines, default=channel)
    current: Message | None = None
    in_extra = False
    sequence = 0
    previous_blank = True
    for line_number, line in enumerate(lines, 1):
        match = HEADER.match(line) if previous_blank else None
        previous_blank = not line.strip()
        if match:
            date, time, author = match.groups()
            try:
                timestamp = datetime.strptime(f"{date} {time}", TIMESTAMP)
            except ValueError:
                if current is not None:
                    current.body.append(line)
                continue
            if current is not None:
                yield current
            pinned = author.endswith(PINNED)
            sequence += 1
            current = Message(
                channel=channel,
                channel_name=channel_name,
                ts=timestamp.strftime("%Y-%m-%d %H:%M"),
                author=author[: -len(PINNED)].strip() if pinned else author.strip(),
                pinned=pinned,
                seq=sequence,
                line=line_number,
            )
            in_extra = False
        elif current is None:
            continue
        elif BRACE_BLOCK.match(line.strip()):
            in_extra = True
            current.extra.append(line)
        elif not line.strip():
            in_extra = False
        elif in_extra:
            current.extra.append(line)
        else:
            current.body.append(line)
    if current is not None:
        yield current


def source_exports(source: GitSource) -> Iterator[tuple[str, bytes]]:
    paths = sorted(
        path for path in source.paths("discord") if path.endswith(".txt")
    )
    if len(paths) != EXPECTED_EXPORTS:
        raise RuntimeError(
            f"{source.commit} has {len(paths)} Discord exports; expected {EXPECTED_EXPORTS}"
        )
    for path in paths:
        yield path, source.read(path)


def populate(
    database: sqlite3.Connection, exports: Iterable[tuple[str, bytes]]
) -> tuple[int, int, Counter[str], Counter[str]]:
    database.executescript(SCHEMA)
    message_id = rune_id = 0
    provenance: list[tuple[str, int, str]] = []
    per_channel: Counter[str] = Counter()
    per_notation: Counter[str] = Counter()

    for path, data in exports:
        channel = PurePosixPath(path).stem
        per_channel[channel] = 0
        provenance.append((path, len(data), hashlib.sha256(data).hexdigest()))
        for message in parse_export(path, data):
            body = "\n".join(message.body).strip()
            extra = "\n".join(message.extra).strip()
            message_id += 1
            per_channel[channel] += 1
            database.execute(
                "INSERT INTO messages "
                "(id,channel,channel_name,ts,author,pinned,body,extra,seq,line) "
                "VALUES (?,?,?,?,?,?,?,?,?,?)",
                (
                    message_id, message.channel, message.channel_name, message.ts,
                    message.author, int(message.pinned), body, extra,
                    message.seq, message.line,
                ),
            )
            database.execute(
                "INSERT INTO msg_fts(rowid,body,extra) VALUES (?,?,?)",
                (message_id, body, extra),
            )

            seen: set[str] = set()
            for run in runes.extract(body):
                if len(run.canon) < MIN_CANON or run.canon in seen:
                    continue
                seen.add(run.canon)
                rune_id += 1
                per_notation[run.notation] += 1
                database.execute(
                    "INSERT INTO runes(id,msg_id,notation,raw,canon,n) VALUES (?,?,?,?,?,?)",
                    (
                        rune_id, message_id, run.notation, run.raw[:MAX_RAW],
                        run.canon, len(run.canon),
                    ),
                )
                database.execute(
                    "INSERT INTO rune_fts(rowid,canon) VALUES (?,?)",
                    (rune_id, run.canon),
                )

    database.executemany(
        "INSERT INTO provenance(file,bytes,sha256) VALUES (?,?,?)", provenance
    )
    database.commit()
    database.execute("PRAGMA optimize")
    database.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    database.execute("PRAGMA journal_mode = DELETE")
    return message_id, rune_id, per_channel, per_notation


def logical_digests(database: sqlite3.Connection) -> dict[str, str]:
    """Hash typed row values independently of SQLite's page layout."""
    result: dict[str, str] = {}
    for table, columns in LOGICAL_TABLES.items():
        digest = hashlib.sha256()
        for row in database.execute(f"SELECT {columns} FROM {table} ORDER BY 1"):
            digest.update(
                json.dumps(
                    tuple(row), ensure_ascii=False, separators=(",", ":")
                ).encode("utf-8")
            )
            digest.update(b"\n")
        result[table] = digest.hexdigest()
    return result


def verify_search_indexes(database: sqlite3.Connection) -> None:
    """Require the pinned FTS definitions and canonical source-table rows."""
    for table, expected_sql in EXPECTED_FTS_SQL.items():
        row = database.execute(
            "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = ?",
            (table,),
        ).fetchone()
        actual_sql = row[0] if row else None
        if actual_sql != expected_sql:
            raise RuntimeError(
                f"{table} definition differs: {actual_sql!r}; expected {expected_sql!r}"
            )

    specifications = (
        ("msg_fts", "messages", ("body", "extra")),
        ("rune_fts", "runes", ("canon",)),
    )
    for index, base, fields in specifications:
        base_count = database.execute(f"SELECT COUNT(*) FROM {base}").fetchone()[0]
        index_count = database.execute(f"SELECT COUNT(*) FROM {index}").fetchone()[0]
        differences = " OR ".join(
            f"search.{field} IS NOT source.{field}" for field in fields
        )
        mismatch_count = database.execute(
            f"SELECT COUNT(*) FROM {base} AS source "
            f"LEFT JOIN {index} AS search ON search.rowid = source.id "
            f"WHERE search.rowid IS NULL OR {differences}"
        ).fetchone()[0]
        if index_count != base_count or mismatch_count:
            raise RuntimeError(
                f"{index} differs from {base}: {index_count}/{base_count} rows, "
                f"{mismatch_count} missing or altered"
            )


def verify_database(
    path: Path, *, expected: bool = True
) -> tuple[dict[str, int], dict[str, str]]:
    uri = f"{path.resolve().as_uri()}?mode=ro"
    with closing(sqlite3.connect(uri, uri=True)) as database:
        if database.execute("PRAGMA quick_check").fetchone()[0] != "ok":
            raise RuntimeError(f"SQLite quick_check failed for {path}")
        columns = [row[1] for row in database.execute("PRAGMA table_info(msg_fts)")]
        if columns != ["body", "extra"]:
            raise RuntimeError(f"msg_fts columns are {columns!r}, expected body and extra")
        verify_search_indexes(database)
        counts = {
            table: database.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            for table in LOGICAL_TABLES
        }
        digests = logical_digests(database)
        if expected and counts != EXPECTED_COUNTS:
            raise RuntimeError(f"logical row counts differ: {counts!r}")
        if expected and digests != EXPECTED_LOGICAL_SHA256:
            raise RuntimeError(f"logical row digests differ: {digests!r}")
        # FTS5 exposes its deepest integrity check through an INSERT control
        # command. Keep the source database genuinely read-only and run that
        # command against an in-memory backup instead.
        with closing(sqlite3.connect(":memory:")) as writable:
            database.backup(writable)
            for table in ("msg_fts", "rune_fts"):
                writable.execute(
                    f"INSERT INTO {table}({table}) VALUES ('integrity-check')"
                )
    return counts, digests


def build_database(
    output: Path,
    *,
    source: GitSource | None = None,
    exports: Iterable[tuple[str, bytes]] | None = None,
    expected: bool = True,
) -> tuple[dict[str, int], dict[str, str]]:
    """Build atomically, validate, and return logical row counts and digests."""
    source = source or GitSource()
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_name(output.name + ".building")
    scratch = [
        temporary,
        temporary.with_name(temporary.name + "-wal"),
        temporary.with_name(temporary.name + "-shm"),
    ]
    for path in scratch:
        path.unlink(missing_ok=True)
    try:
        with closing(sqlite3.connect(temporary)) as database:
            populate(database, exports if exports is not None else source_exports(source))
        counts, digests = verify_database(temporary, expected=expected)
    except BaseException:
        for path in scratch:
            path.unlink(missing_ok=True)
        raise
    temporary.replace(output)
    return counts, digests


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--output", type=Path, default=DISCORD_DB)
    result.add_argument(
        "--check", action="store_true",
        help="rebuild in a temporary directory and compare logical rows with --output",
    )
    return result


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        if args.check:
            if not args.output.is_file():
                raise RuntimeError(f"database does not exist: {args.output}")
            current_counts, current_digests = verify_database(args.output)
            with tempfile.TemporaryDirectory() as temporary:
                rebuilt = Path(temporary) / "discord.db"
                rebuilt_counts, rebuilt_digests = build_database(rebuilt)
            if (current_counts, current_digests) != (rebuilt_counts, rebuilt_digests):
                raise RuntimeError("rebuilt logical database differs from committed database")
            print(f"ok  {current_counts['messages']:,} messages  {args.output}")
            return 0

        counts, digests = build_database(args.output)
        physical = hashlib.sha256(args.output.read_bytes()).hexdigest()
        print(f"wrote {args.output} ({args.output.stat().st_size / 1e6:.1f} MB)")
        print(f"  source commit: {SOURCE_COMMIT}")
        print(f"  messages: {counts['messages']:,}  runes: {counts['runes']:,}")
        print(f"  logical messages sha256: {digests['messages']}")
        print(f"  physical sqlite sha256: {physical}")
        return 0
    except (OSError, RuntimeError, sqlite3.Error, UnicodeError, ValueError) as exc:
        print(f"database build failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
