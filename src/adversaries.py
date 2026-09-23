"""Fabricated histories that each defeat a different signal.

The published result was 2 of 2 fabrications caught. Two is not an evaluation:
both came from the same generator, and the second differed from the first only
in setting `GIT_COMMITTER_DATE`. A detector scored against one trick it already
knows will always look perfect.

So each adversary below is built to beat one specific signal, and the last one
combines all of them. The interesting output is not "caught them all" — it is
**which signal survives** when an adversary is written against it.

  naive            sets only the author date          -> skew
  hidden_skew      sets the committer date too        -> defeats skew
  varied_files     touches several files per commit   -> defeats files_always_one
  varied_messages  writes real-looking subjects       -> defeats subject entropy
  human_hours      commits in working hours only      -> defeats hour entropy
  bursty           clusters work, then rests          -> defeats commits-per-day
  full_stealth     all of the above at once           -> the honest hard case
  backfilled       a genuine repo with fakes inserted -> the realistic case

Nobody publishes a repository admitting its history is fabricated, so a real
positive class cannot be collected. Generating it is the only option and that
is a limitation of the result, not a detail: the detector is measured against
adversaries this project imagined, and a cleverer one may exist.
"""

from __future__ import annotations

import random
import subprocess
import time
from pathlib import Path

ENV_BASE = {
    "GIT_AUTHOR_NAME": "Test Author",
    "GIT_AUTHOR_EMAIL": "test@example.invalid",
    "GIT_COMMITTER_NAME": "Test Author",
    "GIT_COMMITTER_EMAIL": "test@example.invalid",
}

VERBS = [
    "Add",
    "Fix",
    "Refactor",
    "Remove",
    "Document",
    "Test",
    "Rename",
    "Handle",
    "Support",
    "Drop",
    "Simplify",
    "Guard",
    "Cache",
    "Log",
    "Validate",
    "Bump",
    "Inline",
    "Extract",
    "Deprecate",
    "Restore",
]
NOUNS = [
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
    "migration",
    "session",
    "pool",
    "encoder",
    "middleware",
    "fixture",
    "changelog",
    "type hints",
    "edge case",
    "regression",
    "lockfile",
]
TAILS = [
    "",
    "",
    "",
    " on Windows",
    " for empty input",
    " when the cache is cold",
    " in the async path",
    " after a rebase",
    " (#{n})",
    " for Python 3.13",
]


def _run(args: list[str], cwd: Path, env: dict | None = None) -> None:
    full = {**ENV_BASE, **(env or {})}
    import os

    subprocess.run(args, cwd=cwd, check=True, capture_output=True, env={**os.environ, **full})


def _message(rng: random.Random) -> str:
    tail = rng.choice(TAILS).replace("{n}", str(rng.randint(100, 9999)))
    return f"{rng.choice(VERBS)} {rng.choice(NOUNS)}{tail}"


def _touch(target: Path, rng: random.Random, files: int) -> None:
    for _ in range(files):
        path = target / f"mod_{rng.randint(0, 25)}.py"
        existing = path.read_text() if path.exists() else ""
        path.write_text(existing + f"# {rng.random()}\n")


def _working_hour(rng: random.Random, day_epoch: int) -> int:
    """A timestamp inside a plausible working day, weekends rarer."""
    weekday = time.localtime(day_epoch).tm_wday
    if weekday >= 5 and rng.random() > 0.18:  # most weekends are quiet
        return -1
    hour = rng.choice([9, 10, 10, 11, 11, 13, 14, 14, 15, 15, 16, 17, 20, 22])
    return day_epoch + hour * 3600 + rng.randint(0, 3599)


def fabricate(
    target: Path,
    *,
    days: int = 365,
    seed: int = 0,
    hide_skew: bool = False,
    vary_files: bool = False,
    vary_messages: bool = False,
    human_hours: bool = False,
    bursty: bool = False,
) -> Path:
    """One fabricated history, with whichever evasions are switched on."""
    rng = random.Random(seed)
    target.mkdir(parents=True, exist_ok=True)
    _run(["git", "init", "-q", "-b", "main"], target)

    now = int(time.time())
    midnight = now - (now % 86400)

    # Bursty work comes in streaks with gaps; the naive generator commits on a
    # flat random schedule, which is itself a tell.
    active: list[int] = []
    day = days
    while day > 0:
        if bursty:
            streak = rng.randint(2, 9)
            for _ in range(streak):
                if day > 0:
                    active.append(day)
                    day -= 1
            day -= rng.randint(1, 14)
        else:
            if rng.randint(0, 100) <= 80:
                active.append(day)
            day -= 1

    for d in active:
        day_epoch = midnight - d * 86400
        per_day = rng.randint(1, 9) if bursty else rng.randint(1, 5)
        for i in range(per_day):
            stamp = _working_hour(rng, day_epoch) if human_hours else day_epoch + i * 60
            if stamp < 0:
                continue
            iso = time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(stamp))

            if vary_files:
                _touch(target, rng, rng.randint(1, 6))
            else:
                log = target / "README.md"
                existing = log.read_text() if log.exists() else ""
                log.write_text(existing + iso + "\n")

            message = (
                _message(rng) if vary_messages else f"Contribution: {iso[:16].replace('T', ' ')}"
            )
            env = {"GIT_COMMITTER_DATE": iso} if hide_skew else {}
            _run(["git", "add", "-A"], target)
            _run(["git", "commit", "-q", "-m", message, "--date", iso], target, env)
    return target


def genuine(target: Path, commits: int = 120, seed: int = 0) -> Path:
    """A real-looking repo committed normally, as the negative control.

    Without it the detector could be separating "many commits" from "few",
    rather than fabricated from real.
    """
    rng = random.Random(seed)
    target.mkdir(parents=True, exist_ok=True)
    _run(["git", "init", "-q", "-b", "main"], target)
    for _ in range(commits):
        _touch(target, rng, rng.randint(1, 6))
        _run(["git", "add", "-A"], target)
        _run(["git", "commit", "-q", "-m", _message(rng)], target)
    return target


def backfilled(target: Path, seed: int = 0, real: int = 60, fake: int = 200) -> Path:
    """The realistic case: a genuine repo with fabricated history prepended.

    This is what somebody actually does — real work, and a year of invented
    green squares before it. It is the hardest to judge, because every signal
    is diluted by the real half.
    """
    rng = random.Random(seed)
    fabricate(
        target,
        days=150,
        seed=seed,
        hide_skew=True,
        vary_files=True,
        vary_messages=True,
        human_hours=True,
        bursty=True,
    )
    for _ in range(real):
        _touch(target, rng, rng.randint(1, 6))
        _run(["git", "add", "-A"], target)
        _run(["git", "commit", "-q", "-m", _message(rng)], target)
    return target


# name -> (builder, what it is written to defeat)
ADVERSARIES = {
    "naive": (lambda p, s: fabricate(p, days=150, seed=s), "nothing — the baseline forgery"),
    "hidden_skew": (
        lambda p, s: fabricate(p, days=150, seed=s, hide_skew=True),
        "author-to-committer skew",
    ),
    "varied_files": (
        lambda p, s: fabricate(p, days=150, seed=s, hide_skew=True, vary_files=True),
        "one file per commit",
    ),
    "varied_messages": (
        lambda p, s: fabricate(p, days=150, seed=s, hide_skew=True, vary_messages=True),
        "templated subject lines",
    ),
    "human_hours": (
        lambda p, s: fabricate(p, days=150, seed=s, hide_skew=True, human_hours=True),
        "flat hour-of-day distribution",
    ),
    "bursty": (
        lambda p, s: fabricate(p, days=150, seed=s, hide_skew=True, bursty=True),
        "uniform commits per active day",
    ),
    "full_stealth": (
        lambda p, s: fabricate(
            p,
            days=150,
            seed=s,
            hide_skew=True,
            vary_files=True,
            vary_messages=True,
            human_hours=True,
            bursty=True,
        ),
        "every signal at once",
    ),
    "backfilled": (lambda p, s: backfilled(p, seed=s), "every signal, then diluted by real work"),
}
