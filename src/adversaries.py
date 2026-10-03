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
import time
from pathlib import Path

try:
    from gitbuild import HistoryBuilder
except ImportError:  # installed package: only `src.` resolves
    from src.gitbuild import HistoryBuilder

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


def _message(rng: random.Random) -> str:
    tail = rng.choice(TAILS).replace("{n}", str(rng.randint(100, 9999)))
    return f"{rng.choice(VERBS)} {rng.choice(NOUNS)}{tail}"


def _touch(repo: HistoryBuilder, rng: random.Random, files: int) -> None:
    for _ in range(files):
        repo.append(f"mod_{rng.randint(0, 25)}.py", f"# {rng.random()}\n")


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
    repo = HistoryBuilder(target)
    _fabricate_into(
        repo,
        days=days,
        seed=seed,
        hide_skew=hide_skew,
        vary_files=vary_files,
        vary_messages=vary_messages,
        human_hours=human_hours,
        bursty=bursty,
    )
    return repo.finish()


def _fabricate_into(
    repo: HistoryBuilder,
    *,
    days: int,
    seed: int,
    hide_skew: bool,
    vary_files: bool,
    vary_messages: bool,
    human_hours: bool,
    bursty: bool,
) -> None:
    rng = random.Random(seed)
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
                _touch(repo, rng, rng.randint(1, 6))
            else:
                repo.append("README.md", iso + "\n")

            message = (
                _message(rng) if vary_messages else f"Contribution: {iso[:16].replace('T', ' ')}"
            )
            # The naive tool runs `git commit --date`, which leaves the committer
            # date at the moment the forgery was made.
            repo.commit(message, stamp, stamp if hide_skew else now)


def genuine(target: Path, commits: int = 120, seed: int = 0) -> Path:
    """A real-looking repo committed normally, as the negative control.

    Without it the detector could be separating "many commits" from "few",
    rather than fabricated from real.
    """
    rng = random.Random(seed)
    repo = HistoryBuilder(target)
    _commit_normally(repo, rng, commits)
    return repo.finish()


def _commit_normally(repo: HistoryBuilder, rng: random.Random, commits: int) -> None:
    # Committed "now", a second apart, author date == committer date: what a run of
    # plain `git commit` calls in a loop produces.
    start = int(time.time()) - commits
    for i in range(commits):
        _touch(repo, rng, rng.randint(1, 6))
        repo.commit(_message(rng), start + i)


def backfilled(target: Path, seed: int = 0, real: int = 60, fake: int = 200) -> Path:
    """The realistic case: a genuine repo with fabricated history prepended.

    This is what somebody actually does — real work, and a year of invented
    green squares before it. It is the hardest to judge, because every signal
    is diluted by the real half.
    """
    rng = random.Random(seed)
    repo = HistoryBuilder(target)
    _fabricate_into(
        repo,
        days=150,
        seed=seed,
        hide_skew=True,
        vary_files=True,
        vary_messages=True,
        human_hours=True,
        bursty=True,
    )
    _commit_normally(repo, rng, real)
    return repo.finish()


# name -> (builder, what it is written to defeat)
ADVERSARIES = {
    "naive": (lambda p, s: fabricate(p, days=150, seed=s), "nothing - the baseline forgery"),
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


def run(seeds: tuple[int, ...] = (1, 2), controls: int = 3) -> int:
    """Build every adversary on each seed, plus genuine controls, and print the table.

    This is the command behind the adversary table in README.md and docs/RESULTS.md.
    """
    import shutil
    import tempfile

    try:
        from features import fingerprint
        from score import evaluate, verdict
    except ImportError:  # installed package
        from src.features import fingerprint
        from src.score import evaluate, verdict

    def score(repo: Path) -> tuple[int, str, int, list[str]]:
        f = fingerprint(repo)
        signals = evaluate(f)
        label, fired = verdict(signals)
        return f.commits, label, fired, [s.name for s in signals if s.fired]

    work = Path(tempfile.mkdtemp(prefix="chf-adversaries-"))
    flagged = fabricated = total = 0
    defeated: list[str] = []
    try:
        print(f"{'adversary':<17}{'seed':>4}{'commits':>8}  {'verdict':<12}{'flags':>5}  fired")
        print("-" * 96)
        for name, (build, _) in ADVERSARIES.items():
            for seed in seeds:
                n, label, fired, names = score(build(work / f"{name}-{seed}", seed))
                total += 1
                flagged += fired > 0
                fabricated += label == "FABRICATED"
                if fired == 0 and name not in defeated:
                    defeated.append(name)
                print(
                    f"{name:<17}{seed:>4}{n:>8}  {label:<12}{fired:>5}  {', '.join(names) or '-'}"
                )
        false_pos = sum(
            score(genuine(work / f"genuine-{s}", seed=s))[2] > 0 for s in range(controls)
        )
    finally:
        shutil.rmtree(work, ignore_errors=True)
    print()
    print(f"fabrications flagged : {flagged}/{total}")
    print(f"reaching FABRICATED  : {fabricated:>2}/{total}")
    print(f"false positives      : {false_pos}/{controls}   (generated genuine controls)")
    print(f"DEFEATED BY          : {', '.join(defeated) or '-'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
