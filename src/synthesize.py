"""Generate fabricated commit histories, to have ground truth to detect.

This reproduces what contribution-graph generators do - `git commit --date=<past>`
against a single text file - so the detector is evaluated on the real artefact rather
than on a guess about what one looks like.

Everything is written to a temporary directory and never pushed anywhere. The point
is to *detect* these, not to make them: see README for why using one is a bad idea.
"""

from __future__ import annotations

import random
import time
from pathlib import Path

try:
    from gitbuild import HistoryBuilder
except ImportError:  # installed package: only `src.` resolves
    from src.gitbuild import HistoryBuilder


def generate(
    target: Path,
    days: int = 365,
    max_per_day: int = 10,
    frequency: int = 80,
    seed: int = 0,
    hide_skew: bool = False,
) -> Path:
    """Build a repo whose history is entirely fabricated.

    `hide_skew=False` reproduces the naive tool: it sets only the author date, so the
    committer date stays at 'now'. `hide_skew=True` is the harder adversary that also
    sets GIT_COMMITTER_DATE - included so the detector is not evaluated only against
    the easiest possible forgery.
    """
    rng = random.Random(seed)
    repo = HistoryBuilder(target)
    now = int(time.time())

    for day in range(days, 0, -1):
        if rng.randint(0, 100) > frequency:
            continue
        for i in range(rng.randint(1, max_per_day)):
            stamp = now - day * 86400 + i * 60
            message = f"Contribution: {time.strftime('%Y-%m-%d %H:%M', time.localtime(stamp))}"
            repo.append("README.md", message + "\n")
            # `git commit --date` sets only the author date; the committer date stays
            # at the moment the forgery ran, unless the tool also sets it.
            repo.commit(message, stamp, stamp if hide_skew else now)

    return repo.finish()


def generate_realistic(target: Path, commits: int = 40, seed: int = 0) -> Path:
    """A control: a *genuine-looking* small repo, committed normally.

    Without this the detector could be separating 'many commits' from 'few commits'
    rather than fabricated from real.
    """
    rng = random.Random(seed)
    repo = HistoryBuilder(target)
    start = int(time.time()) - commits

    verbs = ["Add", "Fix", "Refactor", "Remove", "Document", "Test", "Rename", "Handle"]
    nouns = [
        "parser",
        "cache",
        "config",
        "client",
        "retry logic",
        "error path",
        "schema",
        "loader",
        "timeout",
        "index",
        "validation",
        "CLI flag",
    ]

    for n in range(commits):
        # Real commits touch a varying number of files.
        for _ in range(rng.randint(1, 6)):
            repo.append(f"mod_{rng.randint(0, 12)}.py", f"# {rng.random()}\n")
        message = f"{rng.choice(verbs)} {rng.choice(nouns)}"
        repo.commit(message, start + n)

    return repo.finish()


if __name__ == "__main__":
    import sys
    import tempfile

    out = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(tempfile.mkdtemp())
    print("generating into", out)
    naive = generate(out / "fake_naive", days=90, max_per_day=5, seed=1)
    print("  fake (naive, author-date only) ->", naive)
    sneaky = generate(out / "fake_hidden", days=90, max_per_day=5, seed=2, hide_skew=True)
    print("  fake (committer date hidden)  ->", sneaky)
    real = generate_realistic(out / "control_real", commits=40, seed=3)
    print("  control (normal commits)      ->", real)
