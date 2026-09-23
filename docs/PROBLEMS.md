# Problems hit while building this

[<- back to README](../README.md)

## 1. An empty repository crashed the scanner

`git log` exits non-zero on a repository that has a branch but no commits. The scanner
raised `RuntimeError` - reporting a failure to *read* the history rather than an empty one.

**Fix:** detect that specific stderr message and return an empty list. The caller decides
what emptiness means; `fingerprint()` raises a clear `ValueError`.

**Test:** `test_empty_repo_raises_clearly`

## 2. A test fixture silently hid a real weakness

Shrinking the `hidden_fake` fixture to 40 days made the test fail: the verdict dropped to
`SUSPICIOUS`. Two of the five signals are gated on a span longer than 60 days, so a shorter
fake defeats them.

The easy move was to lengthen the fixture back to 90 days and say nothing.

**What was done instead:** kept **both**. A 90-day fixture asserts `FABRICATED`, and a
separate 40-day one asserts the weaker verdict. The limitation is now documented in
[LIMITATIONS.md](LIMITATIONS.md) and asserted in
`test_short_hidden_fake_is_only_suspicious`, so it cannot quietly regress.

This is the most useful thing in the repository's history: a failing test revealed a real
limitation, and the limitation was published rather than tuned away.

## 3. CI could not create the test fixtures

The tests build real git repositories with real commits. GitHub's runner has no git
identity configured, so `git commit` refused and every fixture failed.

**Fix:** configure `user.name`, `user.email` and `init.defaultBranch` in the workflow before
running pytest.

## 4. `subprocess.run` lint failure

`ruff` flagged `PLW1510` - missing an explicit `check=` argument - on calls that
deliberately inspect the return code themselves.

**Fix:** passed `check=False` explicitly, with a comment explaining that an empty repository
is a legitimate outcome handled below, not an exception.

## 5. CI cache misconfigured

`setup-uv` errors outright when its default `**/uv.lock` glob matches nothing - a hard job
failure, not a cache miss. No lock file is committed here.

**Fix:** keyed the cache on `pyproject.toml`.

## 6. Scanning a partial clone hung forever, with no error

The obvious way to evaluate this on real histories is to clone forty large projects
blobless - `git clone --filter=blob:none` fetches commits and trees but no file contents,
which is the whole point.

Scoring them produced **nothing at all in 45 minutes**. Not a crash, not a slow trickle of
output: zero bytes.

The cause is `git log --numstat`, which counts added and deleted **lines** and therefore has
to read every blob. On a blobless clone git silently fetches each missing blob from the
promisor remote, one object at a time, over the network. `GIT_NO_LAZY_FETCH=1` makes it
admit this:

```
warning: lazy fetching disabled; some objects may not be available
fatal: could not fetch 2211495b... from promisor remote
```

**Fix:** `--name-only --no-renames`. Paths come from trees, which a blobless clone already
has. Rename detection had to go too - it is on by default since git 2.9 and compares blob
contents to decide whether a delete plus an add is really a rename, which pulls the blobs
straight back in.

On the same clone of `aiohttp`:

| | Result |
|---|---|
| `--numstat` | never completes |
| `--name-only --no-renames` | 14,165 commits, 67,609 paths, **~1 second**, no network |

The line counts were never used - `read_commits` only counts the rows - so nothing was lost.

This one matters beyond the evaluation: anyone who clones a big repository the fast way to
check it would have hit exactly this, and seen a tool that appears to hang.

## 7. Two bugs of my own that would have published wrong numbers

Recorded because both produced confident, plausible output.

**The scoring script recorded every signal, not the fired ones.** `[s.name for s in
signals]` instead of `[s.name for s in signals if s.fired]`, so every row in the results
table claimed all five signals fired. It reads as a finding and is a formatting mistake.

**It also buffered all output until the end**, which is why 45 minutes of a hung run and 45
minutes of a working one looked identical from outside. Progress now prints per repository
and the JSON is rewritten as it goes, so a stall is visible immediately. `python -u` is not
optional when stdout is redirected.
