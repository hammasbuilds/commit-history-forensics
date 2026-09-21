# Limitations

[<- back to README](../README.md)

## The 46/46 result is weaker evidence than it looks

The genuine repositories mostly have **fewer than 15 commits each**, and all are by **one
author**.

Two of the five signals are gated on commit count (10 and 30), and one on a 60-day span.
On repositories this small, **those signals can never fire** - so "zero false positives" is
partly a statement about the evaluation set, not only about the detector.

`score.py` now measures that rather than leaving it as prose. Over the 48 repositories in
the current run:

| signal | exercised on | share |
|---|---:|---:|
| `backdated_commits` | 41 / 48 | 85% |
| `single_file_every_commit` | 33 / 48 | 69% |
| `implausible_cadence` | 33 / 48 | 69% |
| `templated_messages` | 5 / 48 | 10% |
| `saturated_calendar` | 2 / 48 | 4% |

So two of the five signals have essentially no evidence behind them in either direction:
`templated_messages` needs 30 commits and reached 5 repositories, `saturated_calendar` needs
a 60-day span and reached 2. A clean sweep tells you nothing about a signal that never ran.

The defensible claim is **zero false positives across the 33 repositories where the signals
could fire**. A larger and more varied genuine corpus is still the single most valuable next
step - and it is what would let the last two signals be evaluated at all.

## A short, careful forgery escapes

An adversary who **both** sets `GIT_COMMITTER_DATE` **and** keeps the fabricated history
under ~60 days with few commits per day defeats three of the five signals. Only uniformity
still fires, so the verdict is `SUSPICIOUS`, not `FABRICATED`.

This is asserted in `test_short_hidden_fake_is_only_suspicious` rather than hidden.

## Varied files defeat the strongest remaining signal

`single_file_every_commit` is what catches the committer-date-faked forgery. A generator
that writes to several files per commit defeats it, and the remaining signals are weaker.

Nothing here inspects **what** the diffs actually change - only how many files and how
often. A forgery that edits real-looking code across varied files would be considerably
harder to detect.

## Only two fabricated samples

Both were produced by the same synthesiser. Other generators may have different signatures,
and a detector validated against one tool is not validated against the class.

## Heuristics, not a classifier

Thresholds are hand-chosen and stated. That makes them arguable and auditable, which is
deliberate - but it also means they are not calibrated, and the 3-of-5 rule is a convention
rather than a decision boundary derived from data.

## Single-author only

Every repository tested has one author. Real projects have contributor distributions, review
latency and merge patterns - all signals a generator does not reproduce, and none of them
used here.
