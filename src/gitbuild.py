"""Build a real git history in one `git fast-import` process.

The synthetic histories used to be made with one `git add` plus one `git commit`
subprocess per commit. On Windows each spawn costs tens of milliseconds, so a
150-day forgery (several hundred commits) took most of a minute and the test suite
took over ten. fast-import writes the same objects - real commits, real trees, real
author and committer dates - from a single process.

The result is an ordinary repository: `git log` reads it exactly as it reads one
made with `git commit`, which is all the detector ever looks at.
"""

from __future__ import annotations

import os
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path

NAME = "Test Author"
EMAIL = "test@example.invalid"


def _tz(epoch: int) -> str:
    """Local UTC offset at `epoch`, as git writes it (+HHMM)."""
    offset = time.localtime(epoch).tm_gmtoff
    sign = "+" if offset >= 0 else "-"
    offset = abs(offset)
    return f"{sign}{offset // 3600:02d}{(offset % 3600) // 60:02d}"


@dataclass
class HistoryBuilder:
    """Accumulates commits in memory, then writes them all with one fast-import."""

    target: Path
    files: dict[str, str] = field(default_factory=dict)
    _stream: list[bytes] = field(default_factory=list)
    _pending: dict[str, str] = field(default_factory=dict)
    commits: int = 0

    def write(self, path: str, content: str) -> None:
        self.files[path] = content
        self._pending[path] = content

    def append(self, path: str, text: str) -> None:
        self.write(path, self.files.get(path, "") + text)

    def read(self, path: str) -> str:
        return self.files.get(path, "")

    def commit(self, message: str, author_time: int, commit_time: int | None = None) -> None:
        if not self._pending:
            raise ValueError("commit with no changes")
        commit_time = author_time if commit_time is None else commit_time
        msg = message.encode()
        out = [
            b"commit refs/heads/main\n",
            f"author {NAME} <{EMAIL}> {author_time} {_tz(author_time)}\n".encode(),
            f"committer {NAME} <{EMAIL}> {commit_time} {_tz(commit_time)}\n".encode(),
            f"data {len(msg)}\n".encode() + msg + b"\n",
        ]
        for path, content in self._pending.items():
            data = content.encode()
            out.append(f"M 644 inline {path}\ndata {len(data)}\n".encode() + data + b"\n")
        self._stream.append(b"".join(out))
        self._pending.clear()
        self.commits += 1

    def finish(self) -> Path:
        """Init the repo, import every commit, and check out the working tree."""
        self.target.mkdir(parents=True, exist_ok=True)
        env = os.environ.copy()
        _git(["init", "-q", "-b", "main"], self.target, env)
        _git(["fast-import", "--quiet"], self.target, env, b"".join(self._stream))
        if self.commits:
            _git(["checkout", "-q", "-f", "main"], self.target, env)
        return self.target


def _git(args: list[str], cwd: Path, env: dict, stdin: bytes | None = None) -> None:
    # check=False: the error is raised with git's stderr attached, which says far
    # more than CalledProcessError's exit code alone.
    out = subprocess.run(
        ["git", *args], cwd=cwd, env=env, input=stdin, capture_output=True, check=False
    )
    if out.returncode != 0:
        err = out.stderr.decode(errors="replace").strip()[:300]
        raise RuntimeError(f"git {args[0]} failed in {cwd}: {err}")
