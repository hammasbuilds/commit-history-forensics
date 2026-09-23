"""Build four histories in a temp directory and score them. No network, no setup.

    python demo.py

The point of the demo is not that fabrications get caught -- it is *which
adversary survives*. A detector measured against one forgery it already knows
will always look perfect, so the demo builds the genuine control alongside
three fabrications of increasing care and prints what each one costs the
detector.

Takes a few minutes: every repository here is real, built with real `git
commit` calls, because a fabricated history is a property of actual git
objects and cannot be faked with a mock.

The fabrications span 40 days, to keep the demo short. Two of the five signals
are gated on a span over 60 days or 30+ commits, so they cannot fire here and
`hidden_skew` lands on SUSPICIOUS rather than the FABRICATED it draws at 150
days in docs/RESULTS.md. That gap is a documented limitation rather than a
rounding error, so the demo prints it instead of padding the history until it
goes away.
"""

from __future__ import annotations

import shutil
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from adversaries import fabricate, genuine
from features import fingerprint
from score import evaluate, verdict

DAYS = 40

CASES = [
    ("genuine", "a real repository, committed normally", lambda p: genuine(p, commits=120, seed=9)),
    ("naive", "sets only the author date", lambda p: fabricate(p, days=DAYS, seed=1)),
    (
        "hidden_skew",
        "sets the committer date too",
        lambda p: fabricate(p, days=DAYS, seed=1, hide_skew=True),
    ),
    (
        "full_stealth",
        "hides the skew, varies files, messages, hours and cadence",
        lambda p: fabricate(
            p,
            days=DAYS,
            seed=1,
            hide_skew=True,
            vary_files=True,
            vary_messages=True,
            human_hours=True,
            bursty=True,
        ),
    ),
]


def main() -> int:
    work = Path(tempfile.mkdtemp(prefix="chf-demo-"))
    print(f"Building {len(CASES)} real git histories in {work}")
    print("(this takes about a minute - every commit below is a real commit)\n")

    rows = []
    try:
        for name, blurb, build in CASES:
            repo = build(work / name)
            f = fingerprint(repo)
            signals = evaluate(f)
            label, fired = verdict(signals)
            rows.append(
                (name, blurb, f.commits, label, fired, [s.name for s in signals if s.fired])
            )
            print(f"  built {name:<14} {f.commits:>4} commits -> {label}")

        print()
        print(f"{'history':<14}{'commits':>8}  {'verdict':<12}{'flags':>5}  signals that fired")
        print("-" * 96)
        for name, _, commits, label, fired, names in rows:
            print(
                f"{name:<14}{commits:>8}  {label:<12}{fired:>5}  "
                f"{', '.join(names) if names else '-'}"
            )
        print("-" * 96)

        stealth = next(r for r in rows if r[0] == "full_stealth")
        control = next(r for r in rows if r[0] == "genuine")
        print()
        print(
            f"The genuine control is {control[3]} -- without it, the detector could be "
            f"separating\nlarge histories from small ones rather than real from fake."
        )
        print()
        if stealth[4] == 0:
            print(
                "full_stealth is CLEAN: an adversary who defeats every signal at once is\n"
                "invisible to this detector. That is the honest result, and it is the\n"
                "reason the README does not claim a detection rate."
            )
        else:
            print(f"full_stealth still fired {stealth[4]} signal(s): {', '.join(stealth[5])}")
        print()
        print(
            f"These histories span {DAYS} days, to keep the demo short. `saturated_calendar`\n"
            "needs more than 60, so it cannot fire here and the fabrications score one flag\n"
            "lower than they do in docs/RESULTS.md. Keeping a forgery short is itself a\n"
            "documented evasion - see test_short_hidden_fake_is_only_suspicious."
        )
        print("\nSee docs/LIMITATIONS.md for what this cannot do.")
    finally:
        shutil.rmtree(work, ignore_errors=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
