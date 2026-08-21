"""Search the CicadaSolvers archive. Returns conversations, not lines.

Build the index first with `python3 -m tools.build_discord_db`.
"""

from __future__ import annotations

import argparse
import json
import re
import sqlite3
import sys
from contextlib import closing
from typing import NamedTuple

from lib import runes
from lib.paths import DISCORD, DISCORD_DB, ROOT


def die(msg: str) -> SystemExit:
    """Bad query or missing index: message on stderr, exit code 2."""
    print(msg, file=sys.stderr)
    return SystemExit(2)

EXAMPLES = """\
examples:
  python3 -m tools.dsearch "autokey"
  python3 -m tools.dsearch "doublet AND interrupter" --channel 54-55 --since 2021
  python3 -m tools.dsearch --runes ᚠᚢᚦᚩᚱᚳ
  python3 -m tools.dsearch --runes "0 1 2 3 4 5"      # same query, index notation
  python3 -m tools.dsearch --runes "F-U-TH-O-R-C"     # same query, transliteration
  python3 -m tools.dsearch "block" --author .mortlach --window 4
  python3 -m tools.dsearch "vigenere" --json          # machine-readable output

Rune queries are canonicalised, so any notation finds messages written in every
notation; rune hits rank longest matched sequence first, not by relevance.
Hits print with the source file and line number, so a result can be cited as
`discord/54-55.txt:21342`.

exit codes: 0 = ran fine (including zero hits -- a negative result is a
result), 2 = bad query or missing index.
"""

# Sorts after every character that can follow a date prefix, so `--until 2021`
# covers all of 2021 rather than stopping at midnight on the 1st of January.
HIGHEST_CHAR = "￿"

DATE = re.compile(r"^\d{4}(-\d{2}(-\d{2})?)?$")


class Hit(NamedTuple):
    msg_id: int
    channel: str
    seq: int
    note: str  # "" for a text hit; "runic: ᚠᚢᚦ..." for a rune hit


def fts_match(
    db: sqlite3.Connection, sql: str, query: str, params: list, matches: int = 1
) -> tuple[list, str]:
    """Run an FTS query; if the user's syntax is not valid FTS, quote the terms.

    The fallback changes semantics -- every term becomes required and operator
    words become literals -- so it announces itself instead of silently
    answering a different question. Returns (rows, query actually searched).

    `matches` is how many MATCH placeholders the statement binds `query` to.
    """
    try:
        return db.execute(sql, (*[query] * matches, *params)).fetchall(), query
    except sqlite3.OperationalError:
        safe = " ".join(f'"{t}"' for t in re.findall(r"\w+", query))
        if not safe:
            raise die(f"nothing searchable in {query!r}") from None
        print(
            f"note: {query!r} is not valid FTS5 syntax; "
            f"searched {safe!r} instead (every term required, no operators)",
            file=sys.stderr,
        )
        return db.execute(sql, (*[safe] * matches, *params)).fetchall(), safe


def filters(args: argparse.Namespace) -> tuple[str, list]:
    where, params = [], []
    if args.channel:
        where.append("m.channel = ?")
        params.append(args.channel)
    if args.author:
        escaped = re.sub(r"([\\%_])", r"\\\1", args.author)
        where.append(r"m.author LIKE ? ESCAPE '\'")
        params.append(f"%{escaped}%")
    for name in ("since", "until"):
        val = getattr(args, name)
        if val and not DATE.match(val):
            raise die(f"--{name} must be YYYY, YYYY-MM or YYYY-MM-DD, got {val!r}")
    if args.since:
        where.append("m.ts >= ?")
        params.append(args.since)
    if args.until:
        where.append("m.ts <= ?")
        params.append(args.until + HIGHEST_CHAR)
    return (" AND " + " AND ".join(where) if where else ""), params


def check_stale(db: sqlite3.Connection) -> None:
    """Warn when discord/ has changed since the index was built."""
    try:
        rows = db.execute("SELECT file, bytes FROM provenance").fetchall()
    except sqlite3.OperationalError:
        print(
            "note: index predates provenance tracking; rebuild with "
            "python3 -m tools.build_discord_db",
            file=sys.stderr,
        )
        return
    indexed = {r["file"]: r["bytes"] for r in rows}
    current = {
        str(p.relative_to(ROOT)): p.stat().st_size for p in DISCORD.glob("*.txt")
    }
    if indexed != current:
        print(
            "warning: discord/ exports changed since discord.db was built; "
            "results may be stale. rebuild with python3 -m tools.build_discord_db",
            file=sys.stderr,
        )


def search_text(db: sqlite3.Connection, args: argparse.Namespace) -> tuple[list[Hit], str]:
    clause, params = filters(args)
    # Rank on the neighbourhood, match on the message. BM25 divides by document
    # length, so scoring messages alone floats a one-word "autokey" above the
    # analysis answering it; scoring ctx_fts ranks that reply by the discussion
    # it sits in. The message must still match, so a hit always contains the
    # terms it was found by. A context document contains its own message, so the
    # second MATCH only supplies the score -- except under NOT, where a
    # neighbour holding the excluded term drops the hit.
    sql = f"""
        SELECT m.id, m.channel, m.seq, bm25(ctx_fts) AS score
        FROM msg_fts
        JOIN ctx_fts ON ctx_fts.rowid = msg_fts.rowid
        JOIN messages m ON m.id = msg_fts.rowid
        WHERE msg_fts MATCH ? AND ctx_fts MATCH ? {clause}
        ORDER BY score LIMIT ?
    """
    rows, searched = fts_match(db, sql, args.query, [*params, args.limit], matches=2)
    return [Hit(r["id"], r["channel"], r["seq"], "") for r in rows], searched


def search_runes(db: sqlite3.Connection, args: argparse.Namespace) -> tuple[list[Hit], str]:
    try:
        canon, notation = runes.canonicalise_query(args.runes)
    except ValueError as e:
        raise die(str(e)) from None
    if len(canon) < 3:
        raise die("rune queries need at least 3 runes (trigram index)")
    clause, params = filters(args)
    # FTS narrows with trigrams; instr() confirms the exact substring. One hit
    # per message (longest matching run), longest first: length, not relevance,
    # is the only ranking a rune match has.
    sql = f"""
        SELECT m.id, m.channel, m.seq, r.notation, r.raw, MAX(r.n) AS n
        FROM rune_fts JOIN runes r ON r.id = rune_fts.rowid
        JOIN messages m ON m.id = r.msg_id
        WHERE rune_fts MATCH ? AND instr(r.canon, ?) > 0 {clause}
        GROUP BY m.id ORDER BY n DESC LIMIT ?
    """
    try:
        rows = db.execute(sql, (f'"{canon}"', canon, *params, args.limit)).fetchall()
    except sqlite3.OperationalError as e:
        raise die(f"rune query failed: {e}") from None
    print(f"query: {len(canon)} runes, read as {notation}", file=sys.stderr)
    return [
        Hit(r["id"], r["channel"], r["seq"],
            f"{r['notation']}: {' '.join(r['raw'].split())[:100]}")
        for r in rows
    ], notation


def windows(db: sqlite3.Connection, hits: list[Hit], w: int):
    """Merge hits into conversation windows, in reading order."""
    want: dict[str, set[int]] = {}
    notes = {h.msg_id: h.note for h in hits}
    for h in hits:
        want.setdefault(h.channel, set()).update(range(h.seq - w, h.seq + w + 1))

    blocks = []
    for channel, seqs in want.items():
        rows = db.execute(
            "SELECT id, ts, author, pinned, body, extra, seq, line, channel_name"
            f" FROM messages WHERE channel = ? AND seq IN ({','.join('?' * len(seqs))})"
            " ORDER BY seq",
            (channel, *sorted(seqs)),
        ).fetchall()
        run = []
        for r in rows:
            if run and r["seq"] != run[-1]["seq"] + 1:
                blocks.append((channel, run))
                run = []
            run.append(r)
        if run:
            blocks.append((channel, run))
    return blocks, notes


def render_json(blocks, notes: dict[int, str], args: argparse.Namespace, searched: str) -> None:
    src = DISCORD.relative_to(ROOT)
    out = {
        "query": args.runes or args.query,
        "searched": searched,
        "hits": len(notes),
        "conversations": [],
    }
    for channel, msgs in blocks:
        conv = {
            "channel": channel,
            "channel_name": msgs[0]["channel_name"],
            "file": f"{src}/{channel}.txt",
            "messages": [],
        }
        for r in msgs:
            body = r["body"] if args.full else r["body"][: args.chars]
            conv["messages"].append({
                "line": r["line"],
                "ts": r["ts"],
                "author": r["author"],
                "pinned": bool(r["pinned"]),
                "matched": r["id"] in notes,
                "note": notes.get(r["id"], ""),
                "body": body,
                "truncated": len(body) < len(r["body"]),
            })
        out["conversations"].append(conv)
    json.dump(out, sys.stdout, ensure_ascii=False, indent=1)
    print()


def render(blocks, notes: dict[int, str], args: argparse.Namespace) -> None:
    src = DISCORD.relative_to(ROOT)
    for channel, msgs in blocks:
        print(f"\n=== #{msgs[0]['channel_name']}  ·  {src}/{channel}.txt:{msgs[0]['line']} ===")
        for r in msgs:
            mark = ">" if r["id"] in notes else " "
            tag = " [pinned]" if r["pinned"] else ""
            print(f"{mark}   {r['ts']}  {r['author']}{tag}   :{r['line']}")
            if notes.get(r["id"]):
                print(f"{mark}     matched [{notes[r['id']]}]")
            body = r["body"]
            text = body if args.full else body[: args.chars]
            for ln in (text or "(no text)").split("\n"):
                print(f"{mark}     {ln}")
            if len(body) > len(text):
                print(f"{mark}     ... (+{len(body) - len(text)} chars, --full)")
            if r["extra"] and args.full:
                print(f"{mark}     [{r['extra'].splitlines()[0]}]")


def parse_args(argv: list[str] | None = None) -> tuple[argparse.ArgumentParser, argparse.Namespace]:
    ap = argparse.ArgumentParser(
        prog="python3 -m tools.dsearch",
        description="Search the CicadaSolvers Discord archive.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=EXAMPLES,
    )
    ap.add_argument("query", nargs="?", help="full-text query (FTS5 syntax works)")
    ap.add_argument("--runes", help="rune sequence: runic, indices, or transliteration")
    ap.add_argument("--channel", help="restrict to one channel, e.g. 54-55")
    ap.add_argument("--author", help="substring match on author")
    ap.add_argument("--since", help="YYYY or YYYY-MM-DD")
    ap.add_argument("--until", help="YYYY or YYYY-MM-DD")
    ap.add_argument("--limit", type=int, default=8, help="hits (default 8)")
    ap.add_argument("--window", type=int, default=2,
                    help="messages of context each side (default 2)")
    ap.add_argument("--chars", type=int, default=600, help="truncate bodies")
    ap.add_argument("--full", action="store_true", help="no truncation")
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    ap.add_argument("--channels", action="store_true", help="list channels and exit")
    return ap, ap.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    ap, args = parse_args(argv)
    if not DISCORD_DB.exists():
        raise die(f"no index at {DISCORD_DB}. run python3 -m tools.build_discord_db")

    with closing(sqlite3.connect(f"{DISCORD_DB.as_uri()}?mode=ro", uri=True)) as db:
        db.row_factory = sqlite3.Row

        if args.channels:
            for r in db.execute(
                "SELECT channel, channel_name, count(*) n, min(ts) lo, max(ts) hi"
                " FROM messages GROUP BY channel ORDER BY n DESC"
            ):
                print(f"  {r['channel']:20} {r['n']:>7,}  "
                      f"{r['lo'][:7]}..{r['hi'][:7]}  {r['channel_name']}")
            return 0

        if not args.query and not args.runes:
            ap.error("give a query or --runes")

        check_stale(db)
        hits, searched = search_runes(db, args) if args.runes else search_text(db, args)
        if not hits:
            # Zero hits is a result, not a failure: exit 0 so a strict caller
            # records the negative instead of treating it as a crash.
            if args.json:
                json.dump(
                    {"query": args.runes or args.query, "searched": searched,
                     "hits": 0, "conversations": []},
                    sys.stdout, ensure_ascii=False,
                )
                print()
            else:
                print("no hits")
            return 0

        blocks, notes = windows(db, hits, args.window)
        if args.json:
            render_json(blocks, notes, args, searched)
        else:
            render(blocks, notes, args)
            print(f"\n{len(notes)} hits in {len(blocks)} conversations", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
