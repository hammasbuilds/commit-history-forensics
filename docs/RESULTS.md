# Results

[<- back to README](../README.md)

Two questions, answered separately: **does it flag real work?** (it must not) and **does it
catch fabrication?** (it catches some).

Everything below is reproducible with `make scan DIR=<somewhere with git repos>` and
`python demo.py`.

---

## 1. Adversaries: one fabrication per signal

The earlier version of this page reported 2 of 2 fabrications caught. Both came from the
same generator and differed only in setting `GIT_COMMITTER_DATE` - one trick, counted twice.
A detector scored against a trick it already knows will always look perfect.

`src/adversaries.py` builds eight fabrications, each written to defeat a named signal, run
on two seeds each.

| Adversary | Written to defeat | Commits | Verdict | Flags | Signals that fired |
|---|---|---:|---|---:|---|
| `naive` | nothing - the baseline | 337 / 332 | **FABRICATED** | 4 | skew, single-file, templated, saturated |
| `hidden_skew` | author&rarr;committer skew | 337 / 332 | **FABRICATED** | 3 | single-file, templated, saturated |
| `varied_messages` | templated subject lines | 360 / 369 | SUSPICIOUS | 2 | single-file, saturated |
| `human_hours` | flat hour-of-day distribution | 244 / 270 | SUSPICIOUS | 2 | single-file, templated |
| `bursty` | uniform commits per active day | 368 / 391 | SUSPICIOUS | 2 | single-file, templated |
| `varied_files` | one file per commit | 342 / 354 | ONE FLAG | 1 | saturated |
| `full_stealth` | every signal at once | 299 / 247 | **CLEAN** | **0** | - |
| `backfilled` | every signal, then real work | 359 / 307 | **CLEAN** | **0** | - |

```
fabrications flagged : 12/16
reaching FABRICATED  :  4/16
false positives      :  0/3   (generated genuine controls)
DEFEATED BY          : full_stealth, backfilled
```

### What this actually says

**Four of sixteen fabrications were invisible.** The detector catches careless forgery, not
forgery. Every signal is structural, and every one of them is something a generator can be
taught to reproduce.

**`backfilled` is the realistic case.** Take a genuine repository and prepend an invented
year to it - which is what somebody would actually do. Every signal is diluted by the real
half and the medians come out ordinary.

**`varied_files` is the cheapest evasion and scores lowest of the single-evasion set.**
`templated_messages` fires only when `subject_unique_share > 0.98` **and**
`files_always_one`, so varying the files defeats two signals with one change while the
subject lines stay perfectly templated. See the precision note in section 2 for why that
conjunction exists, and `test_the_message_signal_is_gated_on_the_file_signal` for the
assertion that keeps it honest.

---

## 2. Genuine repositories: 86 histories, 178,101 commits

40 established open-source projects cloned blobless (`--filter=blob:none`: commit metadata
and trees, no file contents) plus 46 local repositories.

```
scored               86
with >= 10 commits   71     <- the denominator four of five signals require
total commits        178,101
flagged              0      <- every one would be a false positive
```

### Signal coverage

A clean sweep is only worth the share of the set where a positive was reachable at all.

| signal | floor | exercised on | share | previously |
|---|---|---:|---:|---|
| `backdated_commits` | >= 2 commits | 79 / 86 | 92% | 41/48, 85% |
| `single_file_every_commit` | >= 10 commits | 71 / 86 | 83% | 33/48, 69% |
| `implausible_cadence` | >= 10 commits | 71 / 86 | 83% | 33/48, 69% |
| `templated_messages` | >= 30 commits | 43 / 86 | 50% | 5/48, 10% |
| `saturated_calendar` | > 60 day span | 40 / 86 | 47% | 2/48, 4% |

`templated_messages` and `saturated_calendar` previously ran against 5 and 2 repositories -
a clean sweep says nothing about a signal that never ran. They now run against 43 and 40.

### The conjunction is load-bearing for precision

Eleven genuine repositories exceed the `subject_unique_share > 0.98` threshold that
`templated_messages` tests, including three at exactly 1.000:

| Repository | Commits | `subject_unique_share` | `files_always_one` | Verdict |
|---|---:|---:|---|---|
| `black` | 2,336 | 0.997 | False | CLEAN |
| `tenacity` | 615 | 0.993 | False | CLEAN |
| `python-certifi` | 352 | 0.991 | False | CLEAN |
| `pydantic` | 5,747 | 0.987 | False | CLEAN |
| `tox` | 1,342 | 0.987 | False | CLEAN |
| `pipx` | 1,151 | 0.984 | False | CLEAN |
| `alembic` | 2,094 | 0.981 | False | CLEAN |
| `starlette` | 1,744 | 0.981 | False | CLEAN |
| `classical-computer-vision` | 50 | **1.000** | False | CLEAN |
| `nlp-lab` | 38 | **1.000** | False | CLEAN |
| `code-llm-lab` | 30 | **1.000** | False | CLEAN |

Every one is kept clean **only** by the `files_always_one` half of the conjunction. Without
it, `templated_messages` alone would produce 11 false positives out of 43 exercised
repositories - a 26% false-positive rate on that signal.

That is the trade in full: the conjunction is what makes the signal usable, and the same
conjunction is what lets `varied_files` defeat two signals at once. Both facts are true and
neither is fixable without a signal that reads something other than file counts.

### Skew has no false-positive pressure at all

**Zero of the 86 genuine repositories have a median author&rarr;committer gap above one
day.** Rebases, cherry-picks and patch-based workflows all move the committer date forward,
so the median stays at zero. That is why `backdated_commits` catches `naive` cleanly and why
a single `GIT_COMMITTER_DATE` defeats it permanently.

### Open-source histories (40)

| Repository | Commits | Span (d) | Median skew (d) | Unique subjects | Hour entropy | Verdict |
|---|---:|---:|---:|---:|---:|---|
| `hypothesis` | 17,894 | 4,945 | 0.00 | 0.903 | 4.54 | CLEAN |
| `aiohttp` | 14,165 | 4,740 | 0.00 | 0.884 | 4.40 | CLEAN |
| `mypy` | 13,816 | 5,074 | 0.00 | 0.925 | 4.42 | CLEAN |
| `celery` | 13,332 | 6,360 | 0.00 | 0.842 | 4.29 | CLEAN |
| `textual` | 13,103 | 1,920 | 0.00 | 0.784 | 3.84 | CLEAN |
| `scrapy` | 11,512 | 6,663 | 0.00 | 0.954 | 4.41 | CLEAN |
| `boto3` | 7,910 | 4,402 | 0.00 | 0.730 | 2.64 | CLEAN |
| `fastapi` | 7,713 | 2,828 | 0.00 | 0.535 | 4.30 | CLEAN |
| `requests` | 6,495 | 5,699 | 0.00 | 0.887 | 4.54 | CLEAN |
| `werkzeug` | 6,060 | 7,080 | 0.00 | 0.907 | 4.36 | CLEAN |
| `pydantic` | 5,747 | 3,429 | 0.00 | 0.987 | 4.16 | CLEAN |
| `flask` | 5,557 | 5,999 | 0.00 | 0.900 | 4.39 | CLEAN |
| `isort` | 4,789 | 4,768 | 0.00 | 0.931 | 4.41 | CLEAN |
| `rich` | 4,460 | 2,416 | 0.00 | 0.812 | 4.12 | CLEAN |
| `urllib3` | 4,448 | 6,130 | 0.00 | 0.963 | 4.45 | CLEAN |
| `click` | 3,377 | 4,535 | 0.00 | 0.915 | 4.50 | CLEAN |
| `jinja` | 2,949 | 6,683 | 0.00 | 0.923 | 4.33 | CLEAN |
| `redis-py` | 2,858 | 6,165 | 0.00 | 0.957 | 4.48 | CLEAN |
| `pip-tools` | 2,778 | 5,125 | 0.00 | 0.936 | 4.48 | CLEAN |
| `flake8` | 2,528 | 5,885 | 0.00 | 0.932 | 4.39 | CLEAN |
| `black` | 2,336 | 3,114 | 0.00 | 0.997 | 4.42 | CLEAN |
| `tqdm` | 2,132 | 4,702 | 0.00 | 0.914 | 4.27 | CLEAN |
| `alembic` | 2,094 | 5,990 | 0.00 | 0.981 | 4.00 | CLEAN |
| `attrs` | 1,841 | 4,235 | 0.00 | 0.946 | 4.08 | CLEAN |
| `typer` | 1,762 | 2,454 | 0.00 | 0.549 | 4.27 | CLEAN |
| `starlette` | 1,744 | 3,012 | 0.00 | 0.981 | 4.16 | CLEAN |
| `uvicorn` | 1,566 | 3,399 | 0.00 | 0.969 | 4.19 | CLEAN |
| `httpx` | 1,523 | 2,517 | 0.00 | 0.963 | 3.95 | CLEAN |
| `arrow` | 1,449 | 4,910 | 0.00 | 0.898 | 4.42 | CLEAN |
| `anyio` | 1,421 | 2,971 | 0.00 | 0.939 | 4.20 | CLEAN |
| `tox` | 1,342 | 2,368 | 0.00 | 0.987 | 4.40 | CLEAN |
| `virtualenv` | 1,339 | 2,490 | 0.00 | 0.978 | 4.42 | CLEAN |
| `pipx` | 1,151 | 2,909 | 0.00 | 0.984 | 4.47 | CLEAN |
| `humanize` | 1,087 | 5,458 | 0.00 | 0.935 | 4.43 | CLEAN |
| `markupsafe` | 844 | 5,576 | 0.00 | 0.868 | 4.10 | CLEAN |
| `itsdangerous` | 677 | 5,105 | 0.00 | 0.879 | 4.18 | CLEAN |
| `tenacity` | 615 | 4,973 | 0.00 | 0.993 | 4.24 | CLEAN |
| `python-dotenv` | 438 | 4,813 | 0.00 | 0.957 | 4.34 | CLEAN |
| `records` | 378 | 4,064 | 0.00 | 0.696 | 4.37 | CLEAN |
| `python-certifi` | 352 | 5,355 | 0.00 | 0.991 | 4.16 | CLEAN |

177,582 commits across the 40. The remaining 46 are local repositories totalling 519
commits; 33 of them have fewer than 30 commits, which is why they are reported as part of
the coverage denominator rather than as evidence on their own.

One repository (`assay-drift`) is not readable - `ValueError: no commits` on an initialised
repository with no history. That is the empty-history path, handled and counted as
unreadable rather than as CLEAN.

---

## 3. Reading a partial clone

A note that cost an hour. `read_commits` used `git log --numstat`, which counts added and
deleted **lines** and therefore reads every blob. On a blobless clone - the sensible way to
clone a large repository for a quick check - git fetches those blobs from the promisor
remote one object at a time, over the network, and a scan of `aiohttp` never finishes.

It never errors either, so it looks like a slow repository rather than a bug.

`--name-only --no-renames` reads only trees, which a blobless clone already has. Rename
detection is on by default since git 2.9 and compares blob contents, so it has to be off
too. Measured on the same clone of `aiohttp`:

| | Result |
|---|---|
| `git log --numstat` | never completes; fails immediately with `GIT_NO_LAZY_FETCH=1` |
| `git log --name-only --no-renames` | full history, 67,609 paths, **~1 second**, no network |

The line counts were never used - the code only counts rows - so nothing was lost. The one
behavioural difference is that a pure rename now counts as two touched paths rather than
one, which makes `files_always_one` very slightly harder to trip: the safe direction for a
signal whose false positives matter.
