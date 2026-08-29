"""Search Discord messages, then expand only the useful hits.

Search returns compact individual messages with database ids and stable source
citations. ``show`` retrieves full surrounding conversations for selected ids.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sqlite3
import sys
from contextlib import closing
from datetime import datetime
from typing import NamedTuple

from lib import runes
from lib.paths import DISCORD, DISCORD_DB, ROOT

DEFAULT_LIMIT = 50
DEFAULT_SNIPPET = 240
HIGHEST_CHAR = "￿"
DATE = re.compile(r"^\d{4}(-\d{2}(-\d{2})?)?$")
DATE_FORMATS = {4: "%Y", 7: "%Y-%m", 10: "%Y-%m-%d"}


class Searched(NamedTuple):
    query: str
    notation: str = ""
    indices: tuple[int, ...] = ()


class Hit(NamedTuple):
    id: int
    channel: str
    channel_name: str
    seq: int
    line: int
    ts: str
    author: str
    pinned: bool
    body: str
    extra: str
    note: str = ""


def die(message: str) -> SystemExit:
    print(message, file=sys.stderr)
    return SystemExit(2)


def check_stale(db: sqlite3.Connection) -> None:
    """Warn when the exports differ from the material in the index."""
    try:
        rows = db.execute("SELECT file, bytes, sha256 FROM provenance").fetchall()
    except sqlite3.OperationalError:
        print(
            "warning: discord.db has no provenance; rebuild it with "
            "python3 -m tools.build_discord_db",
            file=sys.stderr,
        )
        return
    indexed = {row["file"]: (row["bytes"], row["sha256"]) for row in rows}
    try:
        sizes = {
            str(path.relative_to(ROOT)): path.stat().st_size
            for path in DISCORD.glob("*.txt")
        }
        current = sizes
        if sizes == {name: size for name, (size, _) in indexed.items()}:
            current = {
                str(path.relative_to(ROOT)): (
                    path.stat().st_size,
                    hashlib.sha256(path.read_bytes()).hexdigest(),
                )
                for path in DISCORD.glob("*.txt")
            }
    except OSError as exc:
        raise die(f"cannot read Discord exports: {exc}") from None
    if indexed != current:
        print(
            "warning: Discord exports changed; rebuild discord.db with "
            "python3 -m tools.build_discord_db",
            file=sys.stderr,
        )


def filters(args: argparse.Namespace) -> tuple[str, list[str]]:
    where: list[str] = []
    params: list[str] = []
    if args.channel:
        where.append("m.channel = ?")
        params.append(args.channel)
    if args.author:
        escaped = re.sub(r"([\\%_])", r"\\\1", args.author)
        where.append(r"m.author LIKE ? ESCAPE '\'")
        params.append(f"%{escaped}%")
    for name in ("since", "until"):
        value = getattr(args, name)
        if not value:
            continue
        try:
            if not DATE.fullmatch(value):
                raise ValueError(value)
            datetime.strptime(value, DATE_FORMATS[len(value)])
        except (KeyError, ValueError):
            raise die(
                f"--{name} must be a real YYYY, YYYY-MM or YYYY-MM-DD date"
            ) from None
    if args.since:
        where.append("m.ts >= ?")
        params.append(args.since)
    if args.until:
        where.append("m.ts <= ?")
        params.append(args.until + HIGHEST_CHAR)
    return (" AND " + " AND ".join(where) if where else ""), params


def fts_rows(
    db: sqlite3.Connection,
    sql: str,
    query: str,
    params: list[object],
) -> tuple[list[sqlite3.Row], str]:
    """Run FTS5 syntax, falling back visibly to an all-token query."""
    try:
        return db.execute(sql, (query, *params)).fetchall(), query
    except sqlite3.OperationalError as exc:
        if "no such table" in str(exc):
            raise die(
                "discord.db predates this search schema; rebuild it with "
                "python3 -m tools.build_discord_db"
            ) from None
        terms = re.findall(r"\w+", query)
        if not terms:
            raise die(f"nothing searchable in {query!r}") from None
        safe = " ".join(f'"{term}"' for term in terms)
        print(
            f"note: invalid FTS5 syntax; searched {safe!r} with every term required",
            file=sys.stderr,
        )
        try:
            return db.execute(sql, (safe, *params)).fetchall(), safe
        except sqlite3.OperationalError as retry:
            raise die(f"search failed: {retry}") from None


def hit_from_row(row: sqlite3.Row, note: str = "") -> Hit:
    return Hit(
        row["id"], row["channel"], row["channel_name"], row["seq"],
        row["line"], row["ts"], row["author"], bool(row["pinned"]),
        row["body"], row["extra"], note,
    )


def search_text(
    db: sqlite3.Connection, args: argparse.Namespace
) -> tuple[list[Hit], Searched, int]:
    clause, params = filters(args)
    sql = f"""
        SELECT m.*, bm25(msg_fts) AS score
        FROM msg_fts JOIN messages m ON m.id = msg_fts.rowid
        WHERE msg_fts MATCH ? {clause}
        ORDER BY score, m.id LIMIT ?
    """
    rows, searched = fts_rows(db, sql, args.query, [*params, args.limit])
    total = db.execute(
        "SELECT COUNT(*) FROM msg_fts JOIN messages m ON m.id = msg_fts.rowid "
        f"WHERE msg_fts MATCH ? {clause}",
        (searched, *params),
    ).fetchone()[0]
    return [hit_from_row(row) for row in rows], Searched(searched), total


def search_runes(
    db: sqlite3.Connection, args: argparse.Namespace
) -> tuple[list[Hit], Searched, int]:
    try:
        canon, notation = runes.canonicalise_query(args.runes)
    except ValueError as exc:
        raise die(str(exc)) from None
    if len(canon) < runes.MIN_INDEXED:
        raise die(f"rune queries need at least {runes.MIN_INDEXED} runes")
    clause, params = filters(args)
    sql = f"""
        SELECT m.*, r.notation, r.raw, MAX(r.n) AS n
        FROM rune_fts JOIN runes r ON r.id = rune_fts.rowid
        JOIN messages m ON m.id = r.msg_id
        WHERE rune_fts MATCH ? AND instr(r.canon, ?) > 0 {clause}
        GROUP BY m.id ORDER BY n DESC, m.id LIMIT ?
    """
    try:
        rows = db.execute(sql, (f'"{canon}"', canon, *params, args.limit)).fetchall()
    except sqlite3.OperationalError as exc:
        raise die(f"rune query failed: {exc}") from None
    indices = tuple(runes.indices_of(canon))
    hits = [
        hit_from_row(row, f"{row['notation']}: {' '.join(row['raw'].split())[:100]}")
        for row in rows
    ]
    total = db.execute(
        "SELECT COUNT(DISTINCT m.id) FROM rune_fts "
        "JOIN runes r ON r.id = rune_fts.rowid "
        "JOIN messages m ON m.id = r.msg_id "
        f"WHERE rune_fts MATCH ? AND instr(r.canon, ?) > 0 {clause}",
        (f'"{canon}"', canon, *params),
    ).fetchone()[0]
    return hits, Searched(canon, notation, indices), total


def compact(text: str, limit: int = DEFAULT_SNIPPET) -> tuple[str, bool]:
    value = " ".join(text.split()) or "(no text)"
    return value[:limit], len(value) > limit


def search_payload(
    args: argparse.Namespace, searched: Searched, hits: list[Hit], total: int
) -> dict:
    results = []
    for hit in hits:
        snippet, truncated = compact(hit.body)
        results.append({
            "id": hit.id,
            "channel": hit.channel,
            "channel_name": hit.channel_name,
            "file": f"discord/{hit.channel}.txt",
            "line": hit.line,
            "ts": hit.ts,
            "author": hit.author,
            "pinned": hit.pinned,
            "body": snippet,
            "truncated": truncated,
            "has_extra": bool(hit.extra),
            "note": hit.note or None,
        })
    return {
        "query": args.runes or args.query,
        "searched": searched.query,
        "notation": searched.notation or None,
        "indices": list(searched.indices) or None,
        "hits": total,
        "shown": len(hits),
        "truncated": len(hits) < total,
        "limit": args.limit,
        "results": results,
    }


def render_search(hits: list[Hit], total: int) -> None:
    if not hits:
        print("no hits -- rephrase the query before drawing a prior-art conclusion")
        return
    for hit in hits:
        pin = " [pinned]" if hit.pinned else ""
        extra = " [attachments/embeds]" if hit.extra else ""
        snippet, truncated = compact(hit.body)
        tail = " …" if truncated else ""
        print(
            f"{hit.id}  discord/{hit.channel}.txt:{hit.line}  "
            f"{hit.ts}  {hit.author}{pin}{extra}"
        )
        if hit.note:
            print(f"    matched {hit.note}")
        print(f"    {snippet}{tail}")
    print(f"\n{len(hits)} of {total} matching messages", file=sys.stderr)


def conversation_rows(
    db: sqlite3.Connection, ids: list[int], window: int
) -> list[tuple[str, list[sqlite3.Row]]]:
    placeholders = ",".join("?" for _ in ids)
    selected = db.execute(
        f"SELECT id, channel, seq FROM messages WHERE id IN ({placeholders})",
        ids,
    ).fetchall()
    found = {row["id"] for row in selected}
    missing = [message_id for message_id in ids if message_id not in found]
    if missing:
        raise die("unknown message ids: " + ", ".join(map(str, missing)))

    by_channel: dict[str, list[tuple[int, int]]] = {}
    for row in selected:
        by_channel.setdefault(row["channel"], []).append(
            (max(1, row["seq"] - window), row["seq"] + window)
        )

    conversations: list[tuple[str, list[sqlite3.Row]]] = []
    for channel, ranges in by_channel.items():
        merged: list[list[int]] = []
        for start, end in sorted(ranges):
            if merged and start <= merged[-1][1] + 1:
                merged[-1][1] = max(merged[-1][1], end)
            else:
                merged.append([start, end])
        for start, end in merged:
            rows = db.execute(
                "SELECT * FROM messages WHERE channel = ? AND seq BETWEEN ? AND ? "
                "ORDER BY seq",
                (channel, start, end),
            ).fetchall()
            conversations.append((channel, rows))
    return conversations


def show_payload(
    conversations: list[tuple[str, list[sqlite3.Row]]], selected: set[int]
) -> dict:
    output = []
    for channel, rows in conversations:
        output.append({
            "channel": channel,
            "channel_name": rows[0]["channel_name"],
            "file": f"discord/{channel}.txt",
            "messages": [
                {
                    "id": row["id"],
                    "line": row["line"],
                    "ts": row["ts"],
                    "author": row["author"],
                    "pinned": bool(row["pinned"]),
                    "selected": row["id"] in selected,
                    "body": row["body"],
                    "extra": row["extra"],
                }
                for row in rows
            ],
        })
    return {"selected": sorted(selected), "conversations": output}


def render_show(
    conversations: list[tuple[str, list[sqlite3.Row]]], selected: set[int]
) -> None:
    for channel, rows in conversations:
        print(
            f"\n=== #{rows[0]['channel_name']}  ·  "
            f"discord/{channel}.txt:{rows[0]['line']} ==="
        )
        for row in rows:
            mark = ">" if row["id"] in selected else " "
            pin = " [pinned]" if row["pinned"] else ""
            print(
                f"{mark} {row['id']}  {row['ts']}  {row['author']}{pin}  "
                f":{row['line']}"
            )
            for line in (row["body"] or "(no text)").splitlines():
                print(f"{mark}   {line}")
            if row["extra"]:
                for line in row["extra"].splitlines():
                    print(f"{mark}   {line}")


def search_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python3 -m tools.dsearch",
        description="Find Discord messages. Use `dsearch show ID...` for context.",
    )
    target = parser.add_mutually_exclusive_group(required=True)
    target.add_argument("query", nargs="?", help="text query; FTS5 syntax is accepted")
    target.add_argument("--runes", help="rune sequence in glyph, index or transliteration form")
    parser.add_argument("--channel")
    parser.add_argument("--author")
    parser.add_argument("--since")
    parser.add_argument("--until")
    parser.add_argument("--limit", type=int, default=DEFAULT_LIMIT)
    parser.add_argument("--json", action="store_true")
    return parser


def show_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python3 -m tools.dsearch show",
        description="Show full conversations around selected search-result ids.",
    )
    parser.add_argument("ids", nargs="+", type=int)
    parser.add_argument("--window", type=int, default=3)
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    try:
        showing = bool(argv and argv[0] == "show")
        args = (show_parser().parse_args(argv[1:]) if showing
                else search_parser().parse_args(argv))
        if showing and args.window < 0:
            raise die("--window must be non-negative")
        if not showing and args.limit < 1:
            raise die("--limit must be positive")
        if not DISCORD_DB.exists():
            raise die(
                "discord.db is missing; build it with python3 -m tools.build_discord_db"
            )

        with closing(sqlite3.connect(f"{DISCORD_DB.as_uri()}?mode=ro", uri=True)) as db:
            db.row_factory = sqlite3.Row
            check_stale(db)
            if showing:
                conversations = conversation_rows(db, args.ids, args.window)
                selected = set(args.ids)
                if args.json:
                    json.dump(
                        show_payload(conversations, selected), sys.stdout,
                        ensure_ascii=False, indent=1,
                    )
                    print()
                else:
                    render_show(conversations, selected)
                return 0

            hits, searched, total = (
                search_runes(db, args) if args.runes else search_text(db, args)
            )
            if args.json:
                json.dump(
                    search_payload(args, searched, hits, total), sys.stdout,
                    ensure_ascii=False, indent=1,
                )
                print()
            else:
                render_search(hits, total)
            return 0
    except SystemExit as exc:
        return exc.code if isinstance(exc.code, int) else 2


if __name__ == "__main__":
    raise SystemExit(main())
