# Limitations

[<- back to README](../README.md)

## Two adversaries defeat it completely

This is the important one. `src/adversaries.py` builds one fabrication per signal, and the
two that combine every evasion are not detected at all:

| Adversary | Verdict | Flags |
|---|---|---:|
| `full_stealth` - hides the skew, varies files, varies messages, commits in working hours, works in bursts | **CLEAN** | 0 |
| `backfilled` - `full_stealth`, then genuine commits on top | **CLEAN** | 0 |

Both ran on two seeds each, at 247-359 commits. Neither fired a single signal.

So the detector catches **careless** fabrication, not fabrication. Every signal here is
structural - timestamps, file counts, subject uniqueness, cadence - and every one of them is
something a generator can be taught to reproduce in an afternoon. The honest framing is that
this raises the cost of a convincing forgery, not that it identifies one.

`backfilled` matters more than `full_stealth`, because it is what somebody would actually
do: take a real repository and prepend an invented year to it. Every signal is diluted by
the genuine half, and the median over the whole history looks ordinary.

## `varied_files` is a two-for-one evasion

`templated_messages` fires only when `subject_unique_share > 0.98` **and**
`files_always_one`. An adversary that varies the files it touches therefore defeats two
signals with one change, and its subject lines can stay perfectly templated.

This is why `varied_files` scores **lower** (1 flag) than `varied_messages`, `human_hours`
and `bursty` (2 flags each) despite hiding less. A conjunction makes a signal precise and it
also makes it cheap to evade.

Asserted in `test_the_message_signal_is_gated_on_the_file_signal` so it cannot regress
quietly.

## The genuine corpus is one author for half of it

The evaluation set is 86 repositories and 178,101 commits: 40 established open-source
projects cloned blobless, and 46 local repositories. The open-source half has real
contributor distributions, review latency and merge patterns. The local half is
single-author, and small - 33 of the 46 have fewer than 30 commits.

Signal coverage over all 86:

| signal | exercised on | share | previously |
|---|---:|---:|---|
| `backdated_commits` | 79 / 86 | 92% | 41/48, 85% |
| `single_file_every_commit` | 71 / 86 | 83% | 33/48, 69% |
| `implausible_cadence` | 71 / 86 | 83% | 33/48, 69% |
| `templated_messages` | 43 / 86 | 50% | 5/48, 10% |
| `saturated_calendar` | 40 / 86 | 47% | 2/48, 4% |

The two signals that previously had essentially no evidence behind them now run against 43
and 40 real repositories. The defensible claim is **zero false positives across the 71
repositories with at least 10 commits**, which is the denominator four of the five signals
require.

What is still missing: no non-English repositories, no monorepos, no repositories with
heavy bot or merge-commit traffic, and nothing from a corporate codebase with enforced
commit conventions - which is exactly the population most likely to look "templated" to this
detector.

## Nothing here reads the diffs

Only how many files a commit touched and how often, never what changed. A forgery that
edits plausible code across varied files is not distinguishable from real work by anything
this measures. That is the ceiling on the whole approach, not a gap in the implementation.

## The positive class is generated, and has to be

Nobody publishes a repository admitting its history is fabricated, so a real positive class
cannot be collected. Every fabrication scored here came from `src/adversaries.py`, which
means the detector is measured against the adversaries this project thought of. A cleverer
one exists and is not represented. Treat 12/16 as a statement about those 16, not a
detection rate.

## Heuristics, not a classifier

Thresholds are hand-chosen and stated beside their reasoning in `src/score.py`. That makes
them arguable and auditable, which is deliberate - but it also means they are not
calibrated, and the 3-of-5 rule is a convention rather than a decision boundary derived
from data.

## A short, careful forgery escapes

An adversary who **both** sets `GIT_COMMITTER_DATE` **and** keeps the fabricated history
under ~60 days with few commits per day defeats three of the five signals, because two are
gated on a span over 60 days or 30 commits. The verdict lands on `SUSPICIOUS`, not
`FABRICATED`.

Asserted in `test_short_hidden_fake_is_only_suspicious`.
