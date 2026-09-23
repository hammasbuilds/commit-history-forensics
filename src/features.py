"""Forensic features of a git history, extracted from `git log` alone.

Every feature here is a *structural* property of how commits were made, not of what
they contain. That matters: a fabricated history can contain plausible-looking code
and still be given away by its timestamps, its uniformity, or its cadence.

Nothing in this module needs the network, a model, or the repository's remote.
"""

from __future__ import annotations

import math
import subprocess
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path

# %H hash | %at author epoch | %ct committer epoch | %s subject
LOG_FORMAT = "%H%x1f%at%x1f%ct%x1f%s"
SEP = "\x1f"


@dataclass
class Commit:
    sha: str
    author_time: int
    commit_time: int
    subject: str
    files: int

    @property
    def date_skew(self) -> int:
        """Seconds between when a change was authored and when the object was made.

        `git commit --date=...` sets ONLY the author date, so a backdated commit keeps
        a committer date of 'now'. That difference is the single loudest signal there
        is, and the common fabrication tools do not hide it.
        """
        return self.commit_time - self.author_time


def read_commits(repo: Path, limit: int | None = None) -> list[Commit]:
    # --name-only, not --numstat, and --no-renames on purpose. Both matter on a
    # partial clone, which is how anyone sensibly clones a large repository to
    # check it: `git clone --filter=blob:none` downloads commits and trees but
    # no file contents.
    #
    #   --numstat counts added and deleted *lines*, so it has to read every
    #   blob. On a blobless clone git fetches them from the promisor remote one
    #   at a time, over the network, and the scan appears to hang forever. This
    #   code never used the line counts - it only counts the rows - so paths
    #   are all it ever needed.
    #
    #   Rename detection is on by default since git 2.9 and compares blob
    #   contents to decide whether a delete plus an add is really a rename,
    #   which drags the blobs back in. For counting how many files a commit
    #   touched, a rename is a touched path either way.
    #
    # Measured on a blobless clone of aiohttp: --numstat could not complete at
    # all, --name-only --no-renames read the full history in about a second.
    #
    # The one behavioural difference: without rename detection a pure rename
    # counts as two paths (the delete and the add) rather than one. That makes
    # `files_always_one` very slightly harder to trip, which is the safe
    # direction for a signal whose false positives matter.
    args = [
        "git",
        "-C",
        str(repo),
        "log",
        f"--pretty=format:{LOG_FORMAT}",
        "--name-only",
        "--no-renames",
    ]
    if limit:
        args.insert(4, f"-n{limit}")
    # check=False on purpose: an empty repo is a legitimate outcome handled below,
    # not an exception.
    out = subprocess.run(args, capture_output=True, text=True, errors="replace", check=False)
    if out.returncode != 0:
        # A freshly-initialised repo has a branch but no commits, and git log exits
        # non-zero for it. That is an empty history, not a failure to read one - the
        # caller decides what to do about emptiness.
        if "does not have any commits yet" in out.stderr:
            return []
        raise RuntimeError(f"git log failed in {repo}: {out.stderr.strip()[:200]}")

    commits: list[Commit] = []
    current: Commit | None = None
    for line in out.stdout.splitlines():
        if SEP in line:
            sha, atime, ctime, subject = line.split(SEP, 3)
            current = Commit(sha, int(atime), int(ctime), subject, 0)
            commits.append(current)
        elif line.strip() and current is not None:
            # one row per path touched by the commit
            current.files += 1
    return commits


def shannon_entropy(values: list[str]) -> float:
    """Bits of entropy in a list of strings. Templated messages score near zero."""
    if not values:
        return 0.0
    counts = Counter(values)
    n = len(values)
    return -sum((c / n) * math.log2(c / n) for c in counts.values())


def _hour_of(epoch: int) -> int:
    # Deliberately UTC: a generator writing at a fixed local hour still lands on a
    # fixed UTC hour, and we are measuring uniformity, not the author's timezone.
    return (epoch // 3600) % 24


@dataclass
class Fingerprint:
    repo: str
    commits: int
    skew_median: float
    skew_nonzero_share: float
    skew_max: int
    files_mean: float
    files_stdev: float
    files_always_one: bool
    subject_entropy: float
    subject_unique_share: float
    hour_entropy: float
    weekend_share: float
    span_days: float
    commits_per_active_day: float
    active_day_share: float

    def as_dict(self) -> dict:
        return asdict(self)


def fingerprint(repo: Path, limit: int | None = None) -> Fingerprint:
    commits = read_commits(repo, limit)
    if not commits:
        raise ValueError(f"no commits found in {repo}")

    n = len(commits)
    skews = sorted(c.date_skew for c in commits)
    files = [c.files for c in commits]
    subjects = [c.subject for c in commits]
    atimes = [c.author_time for c in commits]

    files_mean = sum(files) / n
    variance = sum((f - files_mean) ** 2 for f in files) / n

    days = {t // 86400 for t in atimes}
    span_days = (max(atimes) - min(atimes)) / 86400 or 1.0

    # Monday=0 ... Sunday=6; epoch day 0 (1970-01-01) was a Thursday, hence +3.
    weekend = sum(1 for t in atimes if ((t // 86400) + 3) % 7 >= 5)

    return Fingerprint(
        repo=repo.name,
        commits=n,
        skew_median=float(skews[n // 2]),
        skew_nonzero_share=sum(1 for s in skews if s != 0) / n,
        skew_max=skews[-1],
        files_mean=files_mean,
        files_stdev=math.sqrt(variance),
        files_always_one=all(f == 1 for f in files),
        subject_entropy=shannon_entropy(subjects),
        subject_unique_share=len(set(subjects)) / n,
        hour_entropy=shannon_entropy([str(_hour_of(t)) for t in atimes]),
        weekend_share=weekend / n,
        span_days=span_days,
        commits_per_active_day=n / len(days),
        active_day_share=len(days) / max(span_days, 1.0),
    )


def find_repos(root: Path) -> list[Path]:
    return sorted(p.parent for p in root.glob("*/.git") if p.is_dir())


if __name__ == "__main__":
    import sys

    root = Path(sys.argv[1] if len(sys.argv) > 1 else ".")
    for repo in find_repos(root):
        try:
            f = fingerprint(repo)
        except (RuntimeError, ValueError) as exc:
            print(f"  skip {repo.name}: {exc}")
            continue
        print(
            f"  {f.repo:30} n={f.commits:4} skew_med={f.skew_median:8.0f} "
            f"files_mu={f.files_mean:6.1f} subj_H={f.subject_entropy:5.2f} "
            f"hour_H={f.hour_entropy:4.2f}"
        )
