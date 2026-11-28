"""Branch rules from conventions.md (Git and environments), checked with git.

* Branch names: migrate/wave_NN/<YYYYMMDD-HHMM> and shared/<topic>/<YYYYMMDD-HHMM> (UTC creation time).
* A migrate branch may only change its wave's files, compared with origin/main. Commits from an
  unmerged shared/... branch it merged in (it depends on that shared PR) are not counted.
* A shared branch touching wave files is a warning.
Skipped when git or origin/main isn't available.
"""
import fnmatch

import pytest

from project import MAIN, current_branch, git, parse_branch, shared_base, warn


def owned_globs(wave: str) -> list:
    """Files a wave owner may change (conventions.md, Ownership)."""
    return [
        f"notebooks/{wave}/*",
        f"resources/jobs/{wave}_*.job.yml",
        f"migration/{wave}/*",
        f"tests/waves/{wave}/*",
    ]


WAVE_FILE_GLOBS = owned_globs("wave_[0-9][0-9]")


def is_owned(path: str, globs: list) -> bool:
    return any(fnmatch.fnmatch(path, g) for g in globs)  # fnmatch's * also matches /


def _branch():
    branch = current_branch()
    if branch is None:
        pytest.skip("not a git checkout (or git unavailable)")
    return branch


def _changed_files(base: str):
    """Files changed on this branch since `base`, plus uncommitted and untracked files."""
    out = set()
    for args in (("diff", "--name-only", f"{base}...HEAD"), ("diff", "--name-only", "HEAD"),
                 ("ls-files", "--others", "--exclude-standard")):
        listing = git(*args)
        if listing is None:
            pytest.skip(f"git {' '.join(args)} failed")
        out |= {line for line in listing.splitlines() if line}
    return sorted(out)


def _require_main():
    if git("rev-parse", "--verify", "--quiet", MAIN) is None:
        pytest.skip(f"{MAIN} not available - run git fetch")


def test_branch_name():
    branch = _branch()
    if branch in ("main", "HEAD"):  # HEAD = detached, e.g. in CI
        pytest.skip(f"on {branch}")
    assert parse_branch(branch), (
        f"branch '{branch}' must be migrate/wave_NN/<YYYYMMDD-HHMM> (wave work) or "
        f"shared/<topic>/<YYYYMMDD-HHMM> (shared files); timestamp = branch creation time in UTC"
    )


def test_wave_branch_only_changes_its_wave():
    branch = _branch()
    m = parse_branch(branch)
    if not (m and branch.startswith("migrate/")):
        pytest.skip("not a migrate/... branch")
    _require_main()
    wave, base = m.group("wave"), shared_base(branch)
    outside = [f for f in _changed_files(base) if not is_owned(f, owned_globs(wave))]
    assert not outside, (
        f"{branch} may only change {wave}'s files (compared with {base}). Put shared changes on a "
        f"shared/<topic>/... branch with its own PR (merge it in here if you need it): {outside}"
    )


def test_shared_branch_leaves_wave_files_alone():
    branch = _branch()
    if not (parse_branch(branch) and branch.startswith("shared/")):
        pytest.skip("not a shared/... branch")
    _require_main()
    touched = [f for f in _changed_files(shared_base(branch)) if is_owned(f, WAVE_FILE_GLOBS)]
    if touched:
        warn(f"shared branch changes wave-owned files - get each wave owner's OK in the PR: {touched}")


@pytest.mark.parametrize("name,ok", [
    ("migrate/wave_01/20261126-1015", True),
    ("shared/read-files-incremental/20261126-0930", True),
    ("migrate/wave_01", False),                        # no timestamp
    ("migrate/wave_1/20261126-1015", False),           # wave id must be two digits
    ("migrate/wave_01/20261126-1015-orders", False),   # no session suffix
    ("migrate/wave_01/20261340-1015", False),          # not a real date
    ("migrate/wave_01/2026112-1015", False),           # wrong timestamp format
    ("shared/Read-Files/20261126-0930", False),           # topic must be lowercase
    ("shared/gitignore", False),
    ("feature/x", False),
])
def test_branch_name_format(name, ok):
    assert bool(parse_branch(name)) is ok


@pytest.mark.parametrize("path,wave,expected", [
    ("notebooks/wave_01/01_extract_load.ipynb", "wave_01", True),
    ("notebooks/wave_01/sub/helper.py", "wave_01", True),
    ("resources/jobs/wave_01_orders.job.yml", "wave_01", True),
    ("migration/wave_01/inputs/Job.item", "wave_01", True),
    ("migration/wave_01/scripts/fix_dates.py", "wave_01", True),  # wave-only scripts are the wave's
    ("tests/waves/wave_01/test_wave_01.py", "wave_01", True),
    ("notebooks/wave_02/01_x.ipynb", "wave_01", False),
    ("resources/jobs/wave_010_x.job.yml", "wave_01", False),
    ("src/operators/readers.py", "wave_01", False),
    (".claude/skills/talend-wave-migration/scripts/parse_item.py", "wave_01", False),  # scripts are shared
    ("databricks.yml", "wave_01", False),
    ("AGENTS.md", "wave_01", False),
])
def test_owned_globs(path, wave, expected):
    """Guards the ownership globs themselves."""
    assert is_owned(path, owned_globs(wave)) is expected
