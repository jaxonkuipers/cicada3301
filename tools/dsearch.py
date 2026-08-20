"""Search the CicadaSolvers archive. Returns conversations, not lines.

Build the index first with `python3 -m tools.build_discord_db`.
"""

from __future__ import annotations

import argparse
import re
import sqlite3
import sys
from contextlib import closing
from typing import NamedTuple

from lib import runes
from lib.paths import DISCORD, DISCORD_DB, ROOT

EXAMPLES = """\
examples:
  python3 -m tools.dsearch "autokey"
  python3 -m tools.dsearch "doublet AND interrupter" --channel 54-55 --since 2021
  python3 -m tools.dsearch --runes ᚠᚢᚦᚩᚱᚳ
  python3 -m tools.dsearch --runes "0 1 2 3 4 5"      # same query, index notation
  python3 -m tools.dsearch --runes "F-U-TH-O-R-C"     # same query, transliteration
  python3 -m tools.dsearch "block" --author .mortlach --window 4

Rune queries are canonicalised, so any notation finds messages written in every
notation. Hits print with the source file and line number, so a result can be
cited as `discord/54-55.txt:21342`.
"""

# Sorts after every character that can follow a date prefix, so `--until 2021`
# covers all of 2021 rather than stopping at midnight on the 1st of January.
HIGHEST_CHAR = "￿"


class Hit(NamedTuple):
    msg_id: int
    channel: str
    seq: int
    note: str  # "" for a text hit; "runic: ᚠᚢᚦ..." for a rune hit


def fts_match(
    db: sqlite3.Connection, sql: str, query: str, params: list, matches: int = 1
) -> list:
    """Run an FTS query; if the user's syntax is not valid FTS, quote the terms.

    `matches` is how many MATCH placeholders the statement binds `query` to.
    """
    try:
        return db.execute(sql, (*[query] * matches, *params)).fetchall()
    except sqlite3.OperationalError:
        safe = " ".join(f'"{t}"' for t in re.findall(r"\w+", query))
        if not safe:
            raise SystemExit(f"nothing searchable in {query!r}") from None
        return db.execute(sql, (*[safe] * matches, *params)).fetchall()


def filters(args: argparse.Namespace) -> tuple[str, list]:
    where, params = [], []
    if args.channel:
        where.append("m.channel = ?")
        params.append(args.channel)
    if args.author:
        where.append("m.author LIKE ?")
        params.append(f"%{args.author}%")
    if args.since:
        where.append("m.ts >= ?")
        params.append(args.since)
    if args.until:
        where.append("m.ts <= ?")
        params.append(args.until + HIGHEST_CHAR)
    return (" AND " + " AND ".join(where) if where else ""), params


def search_text(db: sqlite3.Connection, args: argparse.Namespace) -> list[Hit]:
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
    rows = fts_match(db, sql, args.query, [*params, args.limit], matches=2)
    return [Hit(r["id"], r["channel"], r["seq"], "") for r in rows]


def search_runes(db: sqlite3.Connection, args: argparse.Namespace) -> list[Hit]:
    try:
        canon, notation = runes.canonicalise_query(args.runes)
    except ValueError as e:
        raise SystemExit(str(e)) from None
    if len(canon) < 3:
        raise SystemExit("rune queries need at least 3 runes (trigram index)")
    clause, params = filters(args)
    # FTS narrows with trigrams; instr() confirms the exact substring.
    sql = f"""
        SELECT m.id, m.channel, m.seq, r.notation, r.raw
        FROM rune_fts JOIN runes r ON r.id = rune_fts.rowid
        JOIN messages m ON m.id = r.msg_id
        WHERE rune_fts MATCH ? AND instr(r.canon, ?) > 0 {clause}
        ORDER BY r.n DESC LIMIT ?
    """
    try:
        rows = db.execute(sql, (f'"{canon}"', canon, *params, args.limit)).fetchall()
    except sqlite3.OperationalError as e:
        raise SystemExit(f"rune query failed: {e}") from None
    print(f"query: {len(canon)} runes, read as {notation}\n", file=sys.stderr)
    return [
        Hit(r["id"], r["channel"], r["seq"],
            f"{r['notation']}: {' '.join(r['raw'].split())[:100]}")
        for r in rows
    ]


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
    ap.add_argument("--channels", action="store_true", help="list channels and exit")
    return ap, ap.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    ap, args = parse_args(argv)
    if not DISCORD_DB.exists():
        raise SystemExit(f"no index at {DISCORD_DB}. run python3 -m tools.build_discord_db")

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

        hits = search_runes(db, args) if args.runes else search_text(db, args)
        if not hits:
            print("no hits", file=sys.stderr)
            return 1

        blocks, notes = windows(db, hits, args.window)
        render(blocks, notes, args)
    print(f"\n{len(notes)} hits in {len(blocks)} conversations", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
