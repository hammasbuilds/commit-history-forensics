# Future work

[<- back to README](../README.md)

Items 1 and 7 from the earlier version of this page are **done** and are kept here only to
say what changed: the genuine corpus is now 86 repositories and 178,101 commits including
40 established open-source projects, and the positive class is now eight adversaries rather
than one generator's two outputs. See [RESULTS.md](RESULTS.md).

What that work revealed is that the remaining items are no longer a wish list - two of them
are the difference between a detector that works and one that does not.

## 1. Diff-content signals - now the blocking problem

`full_stealth` and `backfilled` are **invisible** to every signal here. Both defeat the
structural family entirely, and nothing short of reading what the commits actually change
will catch them.

Every current signal asks how many files, how often, when. None asks whether a commit
changes meaningful code, rewrites the same line forever, or edits files that have no
relationship to each other. A forgery that varies its file count is already past everything
this project measures.

This is the ceiling on the approach, not a gap in the implementation.

## 2. Multi-author signals

The open-source half of the corpus has real contributor distributions, review latency, merge
commits and co-authored trailers. None of it is used - `fingerprint()` reads only timestamps,
subjects and file counts, and discards the author entirely.

A generator reproduces none of those patterns, which makes this the richest unused family.
It also would not help against `backfilled`, where the real half supplies genuine
collaboration.

## 3. Replace the conjunction in `templated_messages`

`subject_unique_share > 0.98 AND files_always_one` is load-bearing for precision - 11
genuine repositories exceed the uniqueness threshold and are saved only by the file half -
and it is exactly why `varied_files` defeats two signals with one change.

Precision and evadability are the same property here. Fixing it means finding a different
second term, not tuning the first.

## 4. Calibrated scoring

Replace the 3-of-5 rule with a likelihood ratio per signal, producing a probability rather
than a label. The corpus is now large enough to calibrate against - 71 repositories where
the signals can fire - though the positive class is still generated, which limits what a
calibration can honestly claim.

## 5. A corpus that includes the hard negatives

The 86 repositories contain no monorepos, no non-English projects, no heavy bot or
merge-commit traffic, and nothing from a corporate codebase with enforced commit
conventions. That last group is the one most likely to look "templated" to this detector,
and it is entirely absent.

## 6. Ship as a GitHub Action

Report on a pull request, or on a repository when it is first opened. Zero runtime
dependencies makes this unusually easy - and the partial-clone fix means it can check a
large repository in about a second without fetching file contents.

## 7. Test against real generators

The positive class is generated and has to be: nobody publishes a repository admitting its
history is fabricated. Running against the several public contribution-graph tools would at
least show whether the signals generalise beyond the adversaries this project imagined.

Given that `full_stealth` already defeats everything, the expected finding is that the
simple public tools are all caught and none of that means much.
