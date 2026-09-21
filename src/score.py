"""Score a git history for signs of fabrication.

Each signal is reported separately with its own evidence, because a single blended
number tells you nothing about *why* a repo looked suspicious - and because the
signals fail differently. Skew catches only the naive forgery; uniformity catches the
careful one too.

Nothing here is trained. Every threshold is stated in the code with its reasoning, so
a reader can disagree with a specific number rather than with a black box.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from features import Fingerprint, find_repos, fingerprint


@dataclass
class Signal:
    name: str
    fired: bool
    value: float
    detail: str


# A committer date more than an hour after the author date is normal for rebases and
# applied patches; more than a day apart in the MEDIAN means the whole history was
# written at one sitting and backdated.
SKEW_SECONDS = 86_400


def evaluate(f: Fingerprint) -> list[Signal]:
    signals = [
        Signal(
            "backdated_commits",
            f.skew_median > SKEW_SECONDS,
            f.skew_median,
            f"median author->committer gap {f.skew_median / 86400:.1f} days "
            f"(max {f.skew_max / 86400:.1f}). `git commit --date` sets only the author "
            "date, so backdating leaves this gap unless the tool also sets "
            "GIT_COMMITTER_DATE.",
        ),
        Signal(
            "single_file_every_commit",
            f.files_always_one and f.commits >= 10,
            f.files_mean,
            f"every one of {f.commits} commits touched exactly 1 file. Real work "
            "varies; generators edit one log file.",
        ),
        Signal(
            "templated_messages",
            f.subject_unique_share > 0.98 and f.commits >= 30 and f.files_always_one,
            f.subject_unique_share,
            f"{f.subject_unique_share:.0%} of subjects are unique across {f.commits} "
            "commits while every commit touches one file - the signature of a "
            "timestamp-templated message, not of varied work.",
        ),
        Signal(
            "implausible_cadence",
            f.commits_per_active_day > 8 and f.files_always_one,
            f.commits_per_active_day,
            f"{f.commits_per_active_day:.1f} commits per active day, every one a single-file edit.",
        ),
        Signal(
            "saturated_calendar",
            f.active_day_share > 0.7 and f.span_days > 60,
            f.active_day_share,
            f"commits on {f.active_day_share:.0%} of days across "
            f"{f.span_days:.0f} days. Sustained human work is rarely this unbroken.",
        ),
    ]
    return signals


def verdict(signals: list[Signal]) -> tuple[str, int]:
    fired = sum(s.fired for s in signals)
    if fired >= 3:
        return "FABRICATED", fired
    if fired == 2:
        return "SUSPICIOUS", fired
    if fired == 1:
        return "ONE FLAG", fired
    return "CLEAN", 0


def report(repo: Path) -> dict:
    f = fingerprint(repo)
    signals = evaluate(f)
    label, fired = verdict(signals)
    return {
        "repo": f.repo,
        "commits": f.commits,
        "verdict": label,
        "flags": fired,
        "fingerprint": f,
        "signals": signals,
    }


# Each signal has a floor below which it cannot fire at all. A CLEAN verdict on a repo
# under that floor is structurally guaranteed, not a passed test - and counting it as one
# inflates a false-positive rate with repositories the detector never examined.
SIGNAL_FLOOR = {
    "backdated_commits": lambda f: f.commits >= 2,
    "single_file_every_commit": lambda f: f.commits >= 10,
    "templated_messages": lambda f: f.commits >= 30,
    "implausible_cadence": lambda f: f.commits >= 10,
    "saturated_calendar": lambda f: f.span_days > 60,
}


def coverage(scored: list[dict]) -> None:
    """How much of the evaluation set each signal could actually have fired on.

    Printed because "zero false positives across N repositories" is only worth as much as
    the share of those N where a positive was even reachable.
    """
    if not scored:
        return
    total = len(scored)
    print()
    print(f"{'signal':28} {'exercised on':>13}  {'share':>6}")
    print("-" * 52)
    for name, ok in SIGNAL_FLOOR.items():
        n = sum(1 for r in scored if ok(r["fingerprint"]))
        print(f"{name:28} {n:>6} / {total:<4} {n / total:>6.0%}")
    print()
    clean = sum(1 for r in scored if r["verdict"] == "CLEAN")
    testable = sum(1 for r in scored if r["fingerprint"].commits >= 10)
    print(
        f"{clean}/{total} CLEAN, but only {testable} have the >= 10 commits that four of the "
        f"five signals require."
    )
    print("The false-positive claim rests on those, not on the full count.")


if __name__ == "__main__":
    import sys

    roots = [Path(a) for a in sys.argv[1:]] or [Path(".")]
    repos: list[Path] = []
    for root in roots:
        repos.extend(find_repos(root))

    scored: list[dict] = []
    print(f"{'repo':32} {'n':>5}  {'verdict':12} flags  evidence")
    print("-" * 100)
    for repo in repos:
        try:
            r = report(repo)
        except (RuntimeError, ValueError) as exc:
            print(f"{repo.name:32} skipped: {exc}")
            continue
        first = next((s.name for s in r["signals"] if s.fired), "-")
        print(f"{r['repo']:32} {r['commits']:5}  {r['verdict']:12} {r['flags']:5}  {first}")
        scored.append(r)

    coverage(scored)
