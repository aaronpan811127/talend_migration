"""Branch rules from conventions.md (Git and environments), checked with git.

* Branch names: migrate/pattern_NN/<YYYYMMDD-HHMM>-<session> and shared/<topic>/<YYYYMMDD-HHMM>-<session>.
* A migrate branch may only change its pattern's files, compared with its stack base: the closest
  shared/... branch it is stacked on, else origin/main. Shared commits underneath are not counted.
* A shared branch touching pattern files is a warning.
Skipped when git or origin/main isn't available.
"""
import datetime
import fnmatch
import re
import subprocess

import pytest

from project import ROOT, warn

MAIN = "origin/main"
_STAMP = r"(?P<stamp>\d{8}-\d{4})-(?P<session>[a-z0-9][a-z0-9-]{0,39})"
MIGRATE_RX = re.compile(rf"^migrate/(?P<pattern>pattern_\d{{2}})/{_STAMP}$")
SHARED_RX = re.compile(rf"^shared/(?P<topic>[a-z0-9][a-z0-9-]{{0,39}})/{_STAMP}$")


def parse_branch(name: str):
    """Return the regex match for a valid migrate/ or shared/ branch name with a real UTC timestamp, else None."""
    m = MIGRATE_RX.match(name) or SHARED_RX.match(name)
    if not m:
        return None
    try:
        datetime.datetime.strptime(m.group("stamp"), "%Y%m%d-%H%M")
    except ValueError:
        return None
    return m


def owned_globs(pattern: str) -> list:
    """Files a pattern owner may change (conventions.md, Ownership)."""
    return [
        f"notebooks/{pattern}/*",
        f"resources/jobs/{pattern}_*.job.yml",
        f"migration/{pattern}/*",
        f"tests/patterns/{pattern}/*",
    ]


PATTERN_FILE_GLOBS = owned_globs("pattern_[0-9][0-9]")


def is_owned(path: str, globs: list) -> bool:
    return any(fnmatch.fnmatch(path, g) for g in globs)  # fnmatch's * also matches /


def _git(*args):
    try:
        r = subprocess.run(["git", "-C", str(ROOT), *args], capture_output=True, text=True, timeout=60)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return r.stdout.strip() if r.returncode == 0 else None


def _branch():
    branch = _git("rev-parse", "--abbrev-ref", "HEAD")
    if branch is None:
        pytest.skip("not a git checkout (or git unavailable)")
    return branch


def stack_base(branch: str) -> str:
    """The ref this branch is stacked on: the closest shared/... branch (local or origin) that is an
    ancestor of HEAD and ahead of main, else origin/main."""
    refs = _git("for-each-ref", "--format=%(refname:short)", "refs/heads/shared", "refs/remotes/origin/shared") or ""
    best, best_ahead = MAIN, 0
    for ref in refs.splitlines():
        name = ref.removeprefix("origin/")
        if not ref or name == branch or _git("merge-base", "--is-ancestor", ref, "HEAD") is None:
            continue
        ahead = int(_git("rev-list", "--count", f"{MAIN}..{ref}") or 0)
        if ahead > best_ahead:
            best, best_ahead = ref, ahead
    return best


def _changed_files(base: str):
    """Files changed on this branch since `base`, plus uncommitted and untracked files."""
    out = set()
    for args in (("diff", "--name-only", f"{base}...HEAD"), ("diff", "--name-only", "HEAD"),
                 ("ls-files", "--others", "--exclude-standard")):
        listing = _git(*args)
        if listing is None:
            pytest.skip(f"git {' '.join(args)} failed")
        out |= {line for line in listing.splitlines() if line}
    return sorted(out)


def _require_main():
    if _git("rev-parse", "--verify", "--quiet", MAIN) is None:
        pytest.skip(f"{MAIN} not available - run git fetch")


def test_branch_name():
    branch = _branch()
    if branch in ("main", "HEAD"):  # HEAD = detached, e.g. in CI
        pytest.skip(f"on {branch}")
    assert parse_branch(branch), (
        f"branch '{branch}' must be migrate/pattern_NN/<YYYYMMDD-HHMM>-<session> (pattern work) or "
        f"shared/<topic>/<YYYYMMDD-HHMM>-<session> (shared files); timestamp in UTC, session lowercase a-z0-9-"
    )


def test_pattern_branch_only_changes_its_pattern():
    branch = _branch()
    m = parse_branch(branch)
    if not (m and branch.startswith("migrate/")):
        pytest.skip("not a migrate/... branch")
    _require_main()
    pattern, base = m.group("pattern"), stack_base(branch)
    outside = [f for f in _changed_files(base) if not is_owned(f, owned_globs(pattern))]
    assert not outside, (
        f"{branch} may only change {pattern}'s files (compared with {base}). Put shared changes on a "
        f"shared/<topic>/... branch and stack this branch on it: {outside}"
    )


def test_shared_branch_leaves_pattern_files_alone():
    branch = _branch()
    if not (parse_branch(branch) and branch.startswith("shared/")):
        pytest.skip("not a shared/... branch")
    _require_main()
    touched = [f for f in _changed_files(stack_base(branch)) if is_owned(f, PATTERN_FILE_GLOBS)]
    if touched:
        warn(f"shared branch changes pattern-owned files - get each pattern owner's OK in the PR: {touched}")


@pytest.mark.parametrize("name,ok", [
    ("migrate/pattern_01/20261126-1015-orders-load", True),
    ("shared/read-files-incremental/20261126-0930-ops-team", True),
    ("migrate/pattern_01", False),                      # no timestamp/session
    ("migrate/pattern_1/20261126-1015-x", False),       # pattern id must be two digits
    ("migrate/pattern_01/20261126-1015", False),        # no session
    ("migrate/pattern_01/20261340-1015-x", False),      # not a real date
    ("migrate/pattern_01/20261126-1015-Orders", False), # session must be lowercase
    ("shared/gitignore", False),
    ("feature/x", False),
])
def test_branch_name_format(name, ok):
    assert bool(parse_branch(name)) is ok


@pytest.mark.parametrize("path,pattern,expected", [
    ("notebooks/pattern_01/01_extract_load.ipynb", "pattern_01", True),
    ("notebooks/pattern_01/sub/helper.py", "pattern_01", True),
    ("resources/jobs/pattern_01_orders.job.yml", "pattern_01", True),
    ("migration/pattern_01/talend/Job.item", "pattern_01", True),
    ("tests/patterns/pattern_01/test_pattern_01.py", "pattern_01", True),
    ("notebooks/pattern_02/01_x.ipynb", "pattern_01", False),
    ("resources/jobs/pattern_010_x.job.yml", "pattern_01", False),
    ("src/operators/readers.py", "pattern_01", False),
    ("databricks.yml", "pattern_01", False),
    ("AGENTS.md", "pattern_01", False),
])
def test_owned_globs(path, pattern, expected):
    """Guards the ownership globs themselves."""
    assert is_owned(path, owned_globs(pattern)) is expected
