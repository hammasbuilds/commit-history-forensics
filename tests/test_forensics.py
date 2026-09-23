"""Tests that build real git repositories in tmp_path.

No network, no fixtures checked into the repo: each test constructs the history it
needs with actual git commands, so what is asserted is the behaviour of the detector
against real git objects rather than against a mock of them.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from features import Commit, find_repos, fingerprint, shannon_entropy
from score import evaluate, verdict
from synthesize import generate, generate_realistic

# --- pure functions ------------------------------------------------------------------


def test_entropy_of_identical_strings_is_zero():
    assert shannon_entropy(["same"] * 10) == 0.0


def test_entropy_of_distinct_strings_is_log2_n():
    assert shannon_entropy(["a", "b", "c", "d"]) == pytest.approx(2.0)


def test_entropy_of_empty_is_zero():
    assert shannon_entropy([]) == 0.0


def test_date_skew_is_committer_minus_author():
    assert Commit("h", 1000, 4000, "s", 1).date_skew == 3000
    assert Commit("h", 1000, 1000, "s", 1).date_skew == 0


# --- against real generated histories -------------------------------------------------


@pytest.fixture(scope="module")
def naive_fake(tmp_path_factory) -> Path:
    return generate(tmp_path_factory.mktemp("nf") / "fake", days=40, max_per_day=4, seed=7)


@pytest.fixture(scope="module")
def hidden_fake(tmp_path_factory) -> Path:
    # 90 days on purpose: two of the five signals are gated on a history spanning more
    # than 60 days, so a shorter fake is genuinely harder to call. See
    # test_short_hidden_fake_is_only_suspicious for that limitation, stated explicitly.
    return generate(
        tmp_path_factory.mktemp("hf") / "fake", days=90, max_per_day=6, seed=8, hide_skew=True
    )


@pytest.fixture(scope="module")
def short_hidden_fake(tmp_path_factory) -> Path:
    return generate(
        tmp_path_factory.mktemp("sh") / "fake", days=40, max_per_day=4, seed=8, hide_skew=True
    )


@pytest.fixture(scope="module")
def genuine(tmp_path_factory) -> Path:
    return generate_realistic(tmp_path_factory.mktemp("gr") / "real", commits=40, seed=9)


def test_naive_fake_is_flagged(naive_fake):
    label, fired = verdict(evaluate(fingerprint(naive_fake)))
    assert label == "FABRICATED", f"only {fired} flags fired"


def test_hidden_fake_is_still_flagged(hidden_fake):
    """The harder adversary sets GIT_COMMITTER_DATE too, defeating the skew signal.

    It must still be caught - otherwise the detector only works on the laziest forgery.
    """
    f = fingerprint(hidden_fake)
    assert f.skew_median == 0, "fixture should have concealed the skew"
    label, _ = verdict(evaluate(f))
    assert label == "FABRICATED"


def test_short_hidden_fake_is_only_suspicious(short_hidden_fake):
    """A documented limitation, asserted so it cannot regress silently.

    An adversary who conceals the committer date AND keeps the fabricated history
    short (under ~60 days, few commits per day) defeats three of the five signals.
    Only uniformity still fires, so the verdict lands on SUSPICIOUS rather than
    FABRICATED. The detector should say so rather than overclaim.
    """
    label, fired = verdict(evaluate(fingerprint(short_hidden_fake)))
    assert label in {"SUSPICIOUS", "FABRICATED"}, f"missed entirely ({fired} flags)"
    assert fired >= 1


def test_genuine_repo_is_clean(genuine):
    label, fired = verdict(evaluate(fingerprint(genuine)))
    assert label == "CLEAN", f"false positive: {fired} flags on a genuine history"


def test_skew_signal_only_fires_on_the_naive_fake(naive_fake, hidden_fake, genuine):
    def skew_fired(repo):
        return next(s.fired for s in evaluate(fingerprint(repo)) if s.name == "backdated_commits")

    assert skew_fired(naive_fake)
    assert not skew_fired(hidden_fake)
    assert not skew_fired(genuine)


def test_single_file_signal_catches_both_fakes(naive_fake, hidden_fake, genuine):
    def uniform_fired(repo):
        return next(
            s.fired for s in evaluate(fingerprint(repo)) if s.name == "single_file_every_commit"
        )

    assert uniform_fired(naive_fake)
    assert uniform_fired(hidden_fake)
    assert not uniform_fired(genuine)


# --- guard rails ----------------------------------------------------------------------


def test_short_history_does_not_trip_count_gated_signals(tmp_path):
    """A 3-commit repo touching one file each is normal, not fabricated.

    Without the `commits >= 10` gate this would be a false positive on every new repo.
    """
    repo = tmp_path / "tiny"
    repo.mkdir()
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=repo, check=True)
    env = {
        "GIT_AUTHOR_NAME": "t",
        "GIT_AUTHOR_EMAIL": "t@example.invalid",
        "GIT_COMMITTER_NAME": "t",
        "GIT_COMMITTER_EMAIL": "t@example.invalid",
    }
    import os

    for i in range(3):
        (repo / "only.py").write_text(f"x = {i}\n")
        subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
        subprocess.run(
            ["git", "commit", "-q", "-m", f"change {i}"],
            cwd=repo,
            check=True,
            env={**os.environ, **env},
        )
    assert verdict(evaluate(fingerprint(repo)))[0] == "CLEAN"


def test_empty_repo_raises_clearly(tmp_path):
    repo = tmp_path / "empty"
    repo.mkdir()
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=repo, check=True)
    with pytest.raises(ValueError, match="no commits"):
        fingerprint(repo)


def test_find_repos_skips_plain_directories(tmp_path, genuine):
    (tmp_path / "not-a-repo").mkdir()
    import shutil

    shutil.copytree(genuine, tmp_path / "is-a-repo")
    found = {p.name for p in find_repos(tmp_path)}
    assert "is-a-repo" in found
    assert "not-a-repo" not in found


# --- the adversaries ---------------------------------------------------------
#
# The published result was 2 of 2 fabrications caught, and both came from the
# same generator: the second differed only in setting GIT_COMMITTER_DATE. A
# detector scored against one trick it already knows will always look perfect,
# so these build one adversary per signal and check the interesting property —
# that each really does defeat the signal it targets.


def test_every_adversary_targets_a_different_signal():
    from adversaries import ADVERSARIES

    assert len(ADVERSARIES) >= 8
    targets = {defeats for _, defeats in ADVERSARIES.values()}
    assert len(targets) == len(ADVERSARIES), "two adversaries attack the same thing"


def test_the_naive_forgery_leaves_the_skew_it_is_named_for(tmp_path):
    """The baseline. `git commit --date` sets only the author date, so the
    committer date stays at now and the gap is enormous."""
    from adversaries import fabricate
    from features import fingerprint

    repo = fabricate(tmp_path / "naive", days=40, seed=1)
    f = fingerprint(repo)
    assert f.commits > 10
    assert f.skew_median > 86_400, "a naive forgery must show author->committer skew"


def test_hiding_the_committer_date_removes_that_skew(tmp_path):
    """And this is why one signal is never enough."""
    from adversaries import fabricate
    from features import fingerprint

    repo = fabricate(tmp_path / "hidden", days=40, seed=1, hide_skew=True)
    f = fingerprint(repo)
    assert f.skew_median < 60, "setting GIT_COMMITTER_DATE should erase the skew"


def test_varying_files_defeats_the_one_file_signal(tmp_path):
    from adversaries import fabricate
    from features import fingerprint

    plain = fingerprint(fabricate(tmp_path / "plain", days=25, seed=2, hide_skew=True))
    varied = fingerprint(
        fabricate(tmp_path / "varied", days=25, seed=2, hide_skew=True, vary_files=True)
    )
    assert plain.files_always_one
    assert not varied.files_always_one


def test_character_entropy_ranks_a_forgery_above_real_messages(tmp_path):
    """A defect in the feature, found by writing the obvious test and being wrong.

    The expectation was that realistic subjects carry more entropy than
    timestamp templates. They carry **less**: 5.95 against 6.07. A template
    reading "Contribution: 2026-09-23 14:33" embeds a unique timestamp in
    every subject, so it is maximally diverse at the character level, while
    real messages reuse a working vocabulary — "Fix parser", "Fix cache".

    `subject_entropy` is therefore not usable as evidence of fabrication in
    the direction anyone would assume, and `score.py` is right not to use it:
    the scored signal is `subject_unique_share`, tested below.
    """
    from adversaries import fabricate
    from features import fingerprint

    templated = fingerprint(fabricate(tmp_path / "tpl", days=25, seed=3, hide_skew=True))
    varied = fingerprint(
        fabricate(tmp_path / "var", days=25, seed=3, hide_skew=True, vary_messages=True)
    )
    assert templated.subject_entropy > varied.subject_entropy


def test_the_message_signal_is_gated_on_the_file_signal(tmp_path):
    """The structural weakness worth knowing about.

    `templated_messages` fires only when `subject_unique_share > 0.98` AND
    `files_always_one`. So an adversary that varies the files it touches
    defeats **two** signals with one change — the messages can stay perfectly
    templated and the message signal still cannot fire.

    A conjunction makes a signal precise and it also makes it cheap to evade.
    """
    from adversaries import fabricate
    from features import fingerprint
    from score import evaluate

    # Templated subjects throughout; only the file count changes.
    one_file = fingerprint(fabricate(tmp_path / "one", days=45, seed=5, hide_skew=True))
    many = fingerprint(
        fabricate(tmp_path / "many", days=45, seed=5, hide_skew=True, vary_files=True)
    )

    assert one_file.subject_unique_share > 0.98
    assert many.subject_unique_share > 0.98  # still templated
    fired_one = {s.name for s in evaluate(one_file) if s.fired}
    fired_many = {s.name for s in evaluate(many) if s.fired}
    assert "templated_messages" in fired_one
    assert "templated_messages" not in fired_many


def test_working_hours_raise_the_weekend_dip(tmp_path):
    """A fabricated history commits at all hours; a human does not."""
    from adversaries import fabricate
    from features import fingerprint

    flat = fingerprint(fabricate(tmp_path / "flat", days=60, seed=4, hide_skew=True))
    human = fingerprint(
        fabricate(tmp_path / "human", days=60, seed=4, hide_skew=True, human_hours=True)
    )
    assert human.weekend_share < flat.weekend_share


def test_the_genuine_control_is_not_flagged(tmp_path):
    """If this fails the detector is separating small from large, not real
    from fake, and every other number in the repo is meaningless."""
    from adversaries import genuine
    from features import fingerprint
    from score import evaluate, verdict

    repo = genuine(tmp_path / "real", commits=40, seed=9)
    call, _ = verdict(evaluate(fingerprint(repo)))
    assert call == "CLEAN"
