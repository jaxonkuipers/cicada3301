"""Pin the bytes of preserved corpus evidence, including binary artifacts.

The route map and record README files are working indexes.  Preserved identity,
artifact and archived-source files are immutable evidence and are listed in
``corpus/MANIFEST.sha256``.  Deliberate evidence changes must update the
manifest explicitly::

    python3 -m solver.corpus_manifest update
    python3 -m solver.corpus_manifest verify
"""

from __future__ import annotations

import argparse
import hashlib
import os
import tempfile
from pathlib import Path

from solver.paths import CORPUS, ROOT

MANIFEST = CORPUS / "MANIFEST.sha256"
HASH_LENGTH = 64


def _under(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
    except ValueError:
        return False
    return True


def immutable_files() -> tuple[Path, ...]:
    """Return every file in an immutable evidence location."""
    roots = [CORPUS / "identity"]
    records = CORPUS / "records"
    if records.is_dir():
        for record in records.iterdir():
            if not record.is_dir():
                continue
            roots.extend((record / "artifacts", record / "sources"))

    files = {
        path
        for root in roots
        if root.is_dir()
        for path in root.rglob("*")
        if path.is_file() and "__pycache__" not in path.parts
    }
    return tuple(sorted(files, key=lambda path: path.relative_to(ROOT).as_posix()))


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def manifest_text() -> str:
    return "".join(
        f"{sha256(path)}  {path.relative_to(ROOT).as_posix()}\n"
        for path in immutable_files()
    )


def update_manifest() -> None:
    """Atomically replace the manifest with hashes of current evidence."""
    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary = tempfile.mkstemp(prefix=".MANIFEST.", dir=MANIFEST.parent)
    try:
        with os.fdopen(handle, "w", encoding="utf-8", newline="\n") as output:
            output.write(manifest_text())
            output.flush()
            os.fsync(output.fileno())
        Path(temporary).chmod(0o644)
        Path(temporary).replace(MANIFEST)
    except BaseException:
        Path(temporary).unlink(missing_ok=True)
        raise


def _parse_manifest() -> tuple[dict[str, str], list[str]]:
    if not MANIFEST.is_file():
        return {}, [f"missing {_relative(MANIFEST)}"]
    entries: dict[str, str] = {}
    errors: list[str] = []
    for number, line in enumerate(MANIFEST.read_text(encoding="utf-8").splitlines(), 1):
        try:
            digest, relative = line.split("  ", 1)
        except ValueError:
            errors.append(f"manifest line {number} is malformed")
            continue
        if len(digest) != HASH_LENGTH or any(ch not in "0123456789abcdef" for ch in digest):
            errors.append(f"manifest line {number} has an invalid sha256")
            continue
        candidate = (ROOT / relative).resolve()
        if Path(relative).is_absolute() or not _under(candidate, ROOT.resolve()):
            errors.append(f"manifest line {number} leaves the repository")
            continue
        canonical = candidate.relative_to(ROOT.resolve()).as_posix()
        if canonical != relative:
            errors.append(f"manifest line {number} has a non-canonical path")
            continue
        if relative in entries:
            errors.append(f"manifest repeats {relative}")
            continue
        entries[relative] = digest
    return entries, errors


def _relative(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return str(path)


def verify_manifest() -> list[str]:
    """Return all coverage, path and digest errors in the committed manifest."""
    entries, errors = _parse_manifest()
    actual = {_relative(path): path for path in immutable_files()}
    listed = set(entries)
    for relative in sorted(set(actual) - listed):
        errors.append(f"immutable file is not manifested: {relative}")
    for relative in sorted(listed - set(actual)):
        errors.append(f"manifest path is not immutable evidence: {relative}")
    for relative in sorted(listed & set(actual)):
        if sha256(actual[relative]) != entries[relative]:
            errors.append(f"sha256 mismatch: {relative}")
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("verify", "update"), nargs="?", default="verify")
    args = parser.parse_args(argv)
    if args.command == "update":
        update_manifest()
        print(f"wrote {_relative(MANIFEST)} with {len(immutable_files())} files")
        return 0
    errors = verify_manifest()
    if errors:
        for error in errors[:20]:
            print(f"FAIL  {error}")
        if len(errors) > 20:
            print(f"FAIL  {len(errors) - 20} additional manifest errors")
        return 1
    print(f"PASS  {_relative(MANIFEST)} covers {len(immutable_files())} files")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
