"""Build discord.db from the CicadaSolvers exports.

    python3 -m tools.build_discord_db

Turns the flat exports into something you can ask questions of. The point of
this over grep is the rune handling: people write the same rune sequence three
different ways -- as runic codepoints, as Gematria Primus transliterations, and
as index numbers -- and `lib.runes` normalises all three into one canonical
form, so a search in any notation finds messages written in every notation.

Regenerable. Delete discord.db and rerun.
"""

from __future__ import annotations

import hashlib
import re
import sqlite3
import sys
from collections import Counter
from collections.abc import Iterator
from contextlib import closing
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path

from lib import runes
from lib.paths import DISCORD, DISCORD_DB, ROOT

# Strict: message bodies contain lines like "[ᛗ, ᛝ, ᛞ] -> [19, 21, 23]", which a
# loose header pattern happily eats. A real header also always follows a blank
# line (verified across all 109,917 messages), so a quoted header pasted
# mid-paragraph stays body text instead of fabricating a message.
HEADER = re.compile(r"^\[([0-9]{1,2}/[0-9]{1,2}/[0-9]{4}) ([0-9]{1,2}:[0-9]{2} [AP]M)\] (.+)$")
BRACE_BLOCK = re.compile(r"^\{(Embed|Attachments|Reactions|Stickers)\}$")
# Naive local time as DiscordChatExporter wrote it; the exports carry no zone.
TIMESTAMP = "%m/%d/%Y %I:%M %p"
PINNED = " (pinned)"

# Shorter than this and a "sequence" is a coincidence, not a citation. Shared
# with the query path -- see runes.MIN_INDEXED.
MIN_CANON = runes.MIN_INDEXED
# Long enough to recognise a hit by, short enough not to store an essay twice.
MAX_RAW = 400

# The ranking document is a message plus this many neighbours each side. The
# time bound is what keeps it a neighbourhood: in the quiet channels a message
# two places away can be three weeks away, and 23% of +/-2 windows in 23-26
# span over a day.
CONTEXT_WINDOW = 2
CONTEXT_MAX_GAP = timedelta(hours=6)

SCHEMA = """
PRAGMA journal_mode = WAL;

CREATE TABLE messages (
    id           INTEGER PRIMARY KEY,
    channel      TEXT NOT NULL,   -- file stem, e.g. '54-55'
    channel_name TEXT NOT NULL,   -- as exported, e.g. 'Liber-Primus / 54-55-jpg'
    ts           TEXT NOT NULL,   -- ISO 8601, sorts correctly
    author       TEXT NOT NULL,
    pinned       INTEGER NOT NULL DEFAULT 0,
    body         TEXT NOT NULL,   -- human text only
    extra        TEXT NOT NULL,   -- embeds, attachments, reactions
    seq          INTEGER NOT NULL,-- position in channel, for conversation windows
    line         INTEGER NOT NULL -- line in the source .txt, for citation
);
CREATE INDEX msg_channel_seq ON messages(channel, seq);
CREATE INDEX msg_author      ON messages(author);
CREATE INDEX msg_ts          ON messages(ts);

-- English discussion.
CREATE VIRTUAL TABLE msg_fts USING fts5(body, tokenize='unicode61');

-- The same discussion, each message indexed together with its neighbours, for
-- ranking. Contentless: the text is already in messages, and only the term
-- statistics are needed to score.
CREATE VIRTUAL TABLE ctx_fts USING fts5(text, tokenize='unicode61', content='');

-- Rune content, canonicalised across notations. Trigram so an interior
-- substring matches: with the default tokenizer an unspaced rune run is ONE
-- token, and a 6-rune query against a 12-rune message returns nothing.
CREATE TABLE runes (
    id       INTEGER PRIMARY KEY,
    msg_id   INTEGER NOT NULL REFERENCES messages(id),
    notation TEXT NOT NULL,   -- runic | runic-joined | numeric | translit
    raw      TEXT NOT NULL,   -- as written
    canon    TEXT NOT NULL,   -- one char per rune index
    n        INTEGER NOT NULL
);
CREATE INDEX runes_msg ON runes(msg_id);
CREATE VIRTUAL TABLE rune_fts USING fts5(canon, tokenize='trigram');

-- What this db was built from, so a stale index is detectable.
CREATE TABLE provenance (
    file   TEXT PRIMARY KEY,  -- source path relative to the repo root
    bytes  INTEGER NOT NULL,
    sha256 TEXT NOT NULL
);
"""


@dataclass
class Message:
    channel: str
    channel_name: str
    ts: str
    author: str
    pinned: bool
    seq: int
    line: int  # line in the source .txt, for citation
    body: list[str] = field(default_factory=list)
    extra: list[str] = field(default_factory=list)


def channel_name_of(lines: list[str], default: str) -> str:
    for ln in lines[:6]:
        if ln.startswith("Channel:"):
            return ln.split(":", 1)[1].strip()
    return default


def parse_file(path: Path, data: bytes | None = None) -> Iterator[Message]:
    channel = path.stem
    # strict: the exports are clean UTF-8; corruption should fail the build,
    # not silently replace bytes.
    raw = path.read_bytes() if data is None else data
    # read_text() translates newlines and decode() does not, so do it here:
    # a CRLF export otherwise leaves a trailing \r on every body line, which
    # the existing CRLF case caught. \r alone counts too, as universal
    # newlines does.
    lines = raw.decode("utf-8").replace("\r\n", "\n").replace("\r", "\n").split("\n")
    channel_name = channel_name_of(lines, default=channel)

    cur: Message | None = None
    in_extra = False
    seq = 0
    prev_blank = True
    for lineno, ln in enumerate(lines, 1):
        m = HEADER.match(ln) if prev_blank else None
        prev_blank = not ln.strip()
        if m:
            date, time, author = m.groups()
            try:
                ts = datetime.strptime(f"{date} {time}", TIMESTAMP)
            except ValueError:
                # A body line that only looks like a header -- e.g. an impossible
                # date. Keep it as text; closing the message here would emit the
                # one already open a second time.
                if cur is not None:
                    cur.body.append(ln)
                continue
            if cur is not None:
                yield cur
            pinned = author.endswith(PINNED)
            seq += 1
            cur = Message(
                channel=channel,
                channel_name=channel_name,
                ts=ts.strftime("%Y-%m-%d %H:%M"),
                author=author[: -len(PINNED)].strip() if pinned else author.strip(),
                pinned=pinned,
                seq=seq,
                line=lineno,
            )
            in_extra = False
        elif cur is None:
            continue  # export preamble, before the first message
        elif BRACE_BLOCK.match(ln.strip()):
            in_extra = True
            cur.extra.append(ln)
        elif not ln.strip():
            in_extra = False
        elif in_extra:
            cur.extra.append(ln)
        else:
            cur.body.append(ln)
    if cur is not None:
        yield cur


def index_context(db: sqlite3.Connection) -> None:
    """Index every message together with the messages around it.

    BM25 normalises by document length, so scoring a message on its own puts a
    one-word "autokey" above the analysis that answers it. Scoring the
    neighbourhood fixes the ranking; the message itself is still what matches
    and what gets cited.
    """
    for (channel,) in db.execute("SELECT DISTINCT channel FROM messages").fetchall():
        rows = db.execute(
            "SELECT id, ts, body FROM messages WHERE channel = ? ORDER BY seq",
            (channel,),
        ).fetchall()
        stamps = [datetime.fromisoformat(ts) for _, ts, _ in rows]

        def context(i: int, rows=rows, stamps=stamps) -> str:
            lo = max(i - CONTEXT_WINDOW, 0)
            hi = min(i + CONTEXT_WINDOW + 1, len(rows))
            return "\n".join(
                rows[j][2] for j in range(lo, hi)
                if abs(stamps[j] - stamps[i]) <= CONTEXT_MAX_GAP
            )

        db.executemany(
            "INSERT INTO ctx_fts(rowid, text) VALUES (?,?)",
            ((rows[i][0], context(i)) for i in range(len(rows))),
        )


def build(db: sqlite3.Connection) -> tuple[int, int, Counter, Counter]:
    db.executescript(SCHEMA)
    msg_id = rune_id = 0
    provenance: list[tuple[str, int, str]] = []
    per_channel: Counter[str] = Counter()
    per_notation: Counter[str] = Counter()

    for path in sorted(DISCORD.glob("*.txt")):
        per_channel[path.stem] = 0  # keep an empty export visible in the report
        # One read per file: parse and fingerprint from the same bytes, rather
        # than read_text here and read_bytes again for provenance -- 73 MB
        # twice. Same bytes both ways also means provenance cannot record a
        # digest of something other than what was indexed.
        data = path.read_bytes()
        provenance.append((str(path.relative_to(ROOT)), len(data),
                           hashlib.sha256(data).hexdigest()))
        for msg in parse_file(path, data):
            body = "\n".join(msg.body).strip()
            msg_id += 1
            per_channel[path.stem] += 1
            db.execute(
                "INSERT INTO messages"
                "(id,channel,channel_name,ts,author,pinned,body,extra,seq,line)"
                " VALUES (?,?,?,?,?,?,?,?,?,?)",
                (msg_id, msg.channel, msg.channel_name, msg.ts, msg.author,
                 int(msg.pinned), body, "\n".join(msg.extra).strip(), msg.seq, msg.line),
            )
            db.execute("INSERT INTO msg_fts(rowid, body) VALUES (?,?)", (msg_id, body))

            # Dedup on canon alone: the same sequence written twice in one
            # message (or matched as both runic and runic-joined) is one fact,
            # and duplicate rows made one message show up as two hits.
            seen: set[str] = set()
            for run in runes.extract(body):
                if len(run.canon) < MIN_CANON or run.canon in seen:
                    continue
                seen.add(run.canon)
                rune_id += 1
                per_notation[run.notation] += 1
                db.execute(
                    "INSERT INTO runes(id,msg_id,notation,raw,canon,n)"
                    " VALUES (?,?,?,?,?,?)",
                    (rune_id, msg_id, run.notation, run.raw[:MAX_RAW],
                     run.canon, len(run.canon)),
                )
                db.execute(
                    "INSERT INTO rune_fts(rowid, canon) VALUES (?,?)",
                    (rune_id, run.canon),
                )

    db.executemany(
        "INSERT INTO provenance(file, bytes, sha256) VALUES (?,?,?)", provenance
    )

    index_context(db)
    db.commit()
    db.execute("PRAGMA optimize")
    # Leave no WAL sidecars behind: a read-only open fails if they go missing.
    db.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    db.execute("PRAGMA journal_mode = DELETE")
    return msg_id, rune_id, per_channel, per_notation


def main() -> int:
    if not DISCORD.is_dir():
        print(f"no exports at {DISCORD}", file=sys.stderr)
        return 1
    # Build to a temp path and rename. executescript commits the schema, so
    # unlinking first and failing mid-build used to leave a valid but empty
    # discord.db behind -- an index that answers every query with nothing.
    tmp = DISCORD_DB.with_name(DISCORD_DB.name + ".building")
    scratch = (tmp, *(tmp.with_name(tmp.name + s) for s in ("-wal", "-shm")))
    for path in scratch:
        path.unlink(missing_ok=True)
    try:
        with closing(sqlite3.connect(tmp)) as db:
            messages, rune_runs, per_channel, per_notation = build(db)
    except BaseException:
        # All three: the sidecars outlive a failure too, and a stale -wal
        # beside a fresh build is worse than no scratch file at all.
        for path in scratch:
            path.unlink(missing_ok=True)
        raise
    # Only the sidecars: replace() is atomic and overwrites, so unlinking the
    # index first bought nothing and reopened the very window the temp build
    # exists to close -- a kill in between left no index at all.
    for suffix in ("-wal", "-shm"):
        DISCORD_DB.with_name(DISCORD_DB.name + suffix).unlink(missing_ok=True)
    tmp.replace(DISCORD_DB)

    print(f"{DISCORD_DB.relative_to(ROOT)}  ({DISCORD_DB.stat().st_size / 1e6:.1f} MB)")
    print(f"  {messages:,} messages over {len(per_channel)} channels")
    for channel, n in per_channel.most_common():
        print(f"    {channel:24} {n:>7,}")
    print(f"  {rune_runs:,} rune sequences indexed")
    for notation, n in per_notation.most_common():
        print(f"    {notation:24} {n:>7,}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
