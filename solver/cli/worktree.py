"""Create and publish isolated solver wakes.

    python3 -m solver.cli.worktree create cicada-1
    python3 -m solver.cli.worktree publish

Creation starts from the fetched ``origin/main`` commit and records wake
metadata on the unique branch. Publication rebases a clean, committed wake and
pushes its HEAD to ``main`` through the repository's pre-push verification.
"""

from __future__ import annotations

import argparse
import datetime as dt
import os
import re
import subprocess
from pathlib import Path

from solver.paths import ROOT

NAME = re.compile(r"^[a-z0-9][a-z0-9-]{0,47}$")


class WorktreeError(RuntimeError):
    """A wake cannot be created or published safely."""


def validate_name(value: str) -> str:
    value = value.strip().lower().replace("_", "-")
    if not NAME.fullmatch(value):
        raise ValueError("name uses 1-48 lowercase letters, digits or hyphens")
    return value


def _run(runner, args: list[str], *, cwd: Path, check: bool = True,
         capture: bool = False):
    return runner(
        args,
        cwd=cwd,
        check=check,
        text=True,
        capture_output=capture,
    )


def _output(runner, args: list[str], *, cwd: Path) -> str:
    return _run(runner, args, cwd=cwd, capture=True).stdout.strip()


def create(name: str, *, parent: Path | None = None,
           base: str = "origin/main", stamp: str | None = None,
           runner=subprocess.run) -> tuple[Path, str, str]:
    """Fetch the selected base and create a uniquely identified solver wake."""
    name = validate_name(name)
    _run(runner, ["git", "config", "core.hooksPath", ".githooks"], cwd=ROOT)
    _run(runner, ["git", "fetch", "origin", "main"], cwd=ROOT)
    base_sha = _output(runner, ["git", "rev-parse", base], cwd=ROOT)
    stamp = stamp or dt.datetime.now(dt.UTC).strftime("%Y%m%d-%H%M%S")
    wake_id = f"{name}-{stamp}"
    parent = parent or Path(os.environ.get("TMPDIR", "/tmp")) / "cicada-wakes"
    parent.mkdir(parents=True, exist_ok=True)
    path = parent / wake_id
    branch = f"wake/{wake_id}"
    if path.exists():
        raise FileExistsError(path)
    _run(
        runner,
        ["git", "worktree", "add", "-b", branch, str(path), base_sha],
        cwd=ROOT,
    )
    _run(
        runner,
        ["git", "config", f"branch.{branch}.cicadaWake", wake_id],
        cwd=ROOT,
    )
    _run(
        runner,
        ["git", "config", f"branch.{branch}.cicadaBase", base_sha],
        cwd=ROOT,
    )
    return path, branch, base_sha


def _managed_wake(root: Path, runner=subprocess.run) -> tuple[str, str]:
    branch = _output(runner, ["git", "branch", "--show-current"], cwd=root)
    if not branch:
        raise WorktreeError("publication requires a wake branch")
    result = _run(
        runner,
        ["git", "config", "--get", f"branch.{branch}.cicadaWake"],
        cwd=root,
        check=False,
        capture=True,
    )
    wake_id = result.stdout.strip() if result.returncode == 0 else ""
    if not wake_id:
        raise WorktreeError(f"branch {branch!r} has no managed-wake metadata")
    return branch, wake_id


def publish(*, root: Path = ROOT, retries: int = 3,
            runner=subprocess.run) -> tuple[str, str]:
    """Rebase and publish one clean committed wake to origin/main."""
    if retries < 1:
        raise ValueError("retries must be positive")
    branch, wake_id = _managed_wake(root, runner)
    _run(runner, ["git", "config", "core.hooksPath", ".githooks"], cwd=root)
    dirty = _output(runner, ["git", "status", "--porcelain"], cwd=root)
    if dirty:
        raise WorktreeError("commit the wake before publication")

    for attempt in range(1, retries + 1):
        _run(runner, ["git", "fetch", "origin", "main"], cwd=root)
        _run(runner, ["git", "rebase", "origin/main"], cwd=root)
        pushed = _run(
            runner,
            ["git", "push", "origin", "HEAD:main"],
            cwd=root,
            check=False,
        )
        if pushed.returncode == 0:
            break

        _run(runner, ["git", "fetch", "origin", "main"], cwd=root)
        remote_is_base = _run(
            runner,
            ["git", "merge-base", "--is-ancestor", "origin/main", "HEAD"],
            cwd=root,
            check=False,
        )
        if remote_is_base.returncode == 0 or attempt == retries:
            raise WorktreeError("push failed after repository verification")

    _run(runner, ["git", "fetch", "origin", "main"], cwd=root)
    local_sha = _output(runner, ["git", "rev-parse", "HEAD"], cwd=root)
    published = _run(
        runner,
        ["git", "merge-base", "--is-ancestor", local_sha, "origin/main"],
        cwd=root,
        check=False,
    )
    if published.returncode != 0:
        raise WorktreeError("published commit is absent from origin/main")
    return wake_id, local_sha


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python3 -m solver.cli.worktree")
    sub = parser.add_subparsers(dest="command", required=True)
    create_parser = sub.add_parser("create", help="create one isolated solver wake")
    create_parser.add_argument("name", help="short wake or automation name")
    create_parser.add_argument("--base", default="origin/main")
    create_parser.add_argument("--parent", type=Path)
    publish_parser = sub.add_parser("publish", help="rebase and publish this wake")
    publish_parser.add_argument("--retries", type=int, default=3)
    args = parser.parse_args(argv)
    try:
        if args.command == "create":
            path, branch, base_sha = create(
                args.name,
                parent=args.parent,
                base=args.base,
            )
            print(f"worktree: {path}")
            print(f"branch: {branch}")
            print(f"base: {base_sha}")
            print(f"continue in: {path}")
            print("publish committed checkpoints with: python3 -m solver.cli.worktree publish")
        else:
            wake_id, commit = publish(retries=args.retries)
            print(f"published {wake_id} at {commit} to origin/main")
    except (ValueError, FileExistsError, WorktreeError,
            subprocess.CalledProcessError) as exc:
        print(f"worktree {args.command} failed: {exc}")
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
