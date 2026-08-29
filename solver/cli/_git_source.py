"""Read versioned source assets without restoring them to the worktree."""

from __future__ import annotations

import subprocess
from collections.abc import Callable
from pathlib import Path, PurePosixPath

from solver.paths import ROOT

SOURCE_COMMIT = "71b0ebab3823dcff8c41674f3b1b4ffad5c91171"

Runner = Callable[..., subprocess.CompletedProcess[bytes]]


def _path(value: str) -> str:
    path = PurePosixPath(value)
    if path.is_absolute() or ".." in path.parts or value != path.as_posix():
        raise ValueError(f"source path must be a normalized repository path: {value!r}")
    return value


class GitSource:
    """A read-only view of files committed in one local Git snapshot."""

    def __init__(
        self,
        commit: str = SOURCE_COMMIT,
        *,
        root: Path = ROOT,
        runner: Runner = subprocess.run,
    ) -> None:
        self.commit = commit
        self.root = root
        self.runner = runner

    def _run(self, *args: str) -> bytes:
        result = self.runner(
            ["git", *args],
            cwd=self.root,
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        if result.returncode:
            detail = result.stderr.decode("utf-8", errors="replace").strip()
            raise RuntimeError(f"git {' '.join(args)} failed: {detail}")
        return result.stdout

    def paths(self, prefix: str) -> tuple[str, ...]:
        prefix = _path(prefix)
        raw = self._run("ls-tree", "-r", "--name-only", self.commit, "--", prefix)
        return tuple(line for line in raw.decode("utf-8").splitlines() if line)

    def read(self, path: str) -> bytes:
        path = _path(path)
        return self._run("show", f"{self.commit}:{path}")
