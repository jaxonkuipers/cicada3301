"""Rebuild the frozen English-through-Gematria-Primus model.

The source prose stays in Git commit ``71b0eba`` rather than the current
worktree. This command reads those local Git objects directly; it performs no
network access.
"""

from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import io
import json
import sys
from collections import Counter
from pathlib import Path

from solver.cli._git_source import GitSource
from solver.corpus import GematriaPrimus
from solver.paths import ROOT

OUTPUT = ROOT / "solver" / "data" / "english_model.json.gz"
REFERENCE_PREFIX = "reference/english"
MABINOGION = "corpus/2012/mabinogion/translation.txt"
SENTENCES = "corpus/2014/liber-primus/sentences.csv"
GEMATRIA = "corpus/2013/gematria-primus/table.csv"
EXPECTED_SHA256 = "14509e5d79260f7e3a48dbd53dd95ffe9844c51ab29347e79fb0b2b2e44b2c5d"


def _text(source: GitSource, path: str) -> str:
    return source.read(path).decode("utf-8")


def _gematria(source: GitSource) -> GematriaPrimus:
    rows = list(csv.DictReader(io.StringIO(_text(source, GEMATRIA))))
    rows.sort(key=lambda row: int(row["index"]))
    return GematriaPrimus(
        runes=tuple(row["rune"] for row in rows),
        primes=tuple(int(row["prime"]) for row in rows),
        translits=tuple(row["transliteration"] for row in rows),
    )


def training_indices(source: GitSource) -> tuple[int, ...]:
    """Return the exact rune stream used by the former runtime model."""
    gp = _gematria(source)
    sentence_rows = csv.DictReader(io.StringIO(_text(source, SENTENCES)))
    parts = [_text(source, MABINOGION)]
    parts.extend(row["english"] for row in sentence_rows if row["english"])
    reference_paths = sorted(
        path for path in source.paths(REFERENCE_PREFIX) if path.endswith(".txt")
    )
    parts.extend(_text(source, path) for path in reference_paths)
    return tuple(index for part in parts for index in gp.spell(part))


def _code(gram: tuple[int, ...], base: int) -> int:
    value = 0
    for index in gram:
        value = value * base + index
    return value


def model_bytes(source: GitSource | None = None) -> bytes:
    """Create deterministic gzip bytes for the sufficient statistics."""
    source = source or GitSource()
    indices = training_indices(source)
    counts: dict[str, list[list[int]]] = {}
    for order in range(1, 5):
        grams = Counter(
            tuple(indices[start : start + order])
            for start in range(len(indices) - order + 1)
        )
        counts[str(order)] = [
            [_code(gram, 29), count] for gram, count in sorted(grams.items())
        ]
    payload = {
        "alphabet_size": 29,
        "counts": counts,
        "format": 1,
        "max_order": 4,
        "training_length": len(indices),
        "training_sha256": hashlib.sha256(bytes(indices)).hexdigest(),
    }
    raw = json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    target = io.BytesIO()
    with gzip.GzipFile(fileobj=target, mode="wb", filename="", mtime=0) as stream:
        stream.write(raw)
    return target.getvalue()


def write_model(output: Path, data: bytes) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_name(output.name + ".building")
    temporary.write_bytes(data)
    temporary.replace(output)


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--output", type=Path, default=OUTPUT)
    result.add_argument(
        "--check", action="store_true",
        help="rebuild in memory and compare with --output without writing",
    )
    return result


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        data = model_bytes()
    except (RuntimeError, UnicodeError, ValueError) as exc:
        print(f"model build failed: {exc}", file=sys.stderr)
        return 1
    digest = hashlib.sha256(data).hexdigest()
    if digest != EXPECTED_SHA256:
        print(
            f"model digest {digest} differs from pinned {EXPECTED_SHA256}",
            file=sys.stderr,
        )
        return 1
    if args.check:
        if not args.output.is_file() or args.output.read_bytes() != data:
            print(f"{args.output} differs from the reproducible model", file=sys.stderr)
            return 1
        print(f"ok  {digest}  {args.output}")
        return 0
    write_model(args.output, data)
    print(f"wrote {args.output} ({len(data):,} bytes, sha256 {digest})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
