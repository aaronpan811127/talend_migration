"""Static checks on migration/<pattern>/checkpoint.yml - the pattern's progress, shared by every session
that works on its branch. Rules: skills/talend-pattern-migration/references/conventions.md#checkpoint
"""
import datetime
import re

import pytest

from project import current_branch, inventory_rows, load_yaml, parse_branch, pattern_dirs, stack_base, warn

STEPS = ["setup", "analyze", "spec", "convert", "job_yamls", "tests", "validate", "pr_review", "done"]
FIELDS = {"pattern", "branch", "base", "prs", "step", "updated", "done", "next", "blocked_on", "notes"}
REQUIRED = {"pattern", "branch", "base", "prs", "step", "updated", "done", "next"}
PR_RX = re.compile(r"^(#?\d+|https://github\.com/[^/\s]+/[^/\s]+/pull/\d+)$")


def _statuses(pattern):
    return {r["status"] for r in inventory_rows() if r["pattern"] == pattern}


def _load(folder):
    path = folder / "checkpoint.yml"
    if not path.is_file():
        started = _statuses(folder.name) - {"not_started"}
        assert not started, f"checkpoint.yml is required once work has started (jobs.csv statuses: {sorted(started)})"
        pytest.skip("no checkpoint.yml yet (pattern not started)")
    return load_yaml(path)


@pytest.mark.parametrize("folder", pattern_dirs(), ids=lambda p: p.name)
class TestCheckpoint:
    def test_fields(self, folder):
        cp = _load(folder)
        assert not (REQUIRED - set(cp)), f"missing fields {sorted(REQUIRED - set(cp))}"
        assert not (set(cp) - FIELDS), f"unknown fields {sorted(set(cp) - FIELDS)}"
        assert cp["pattern"] == folder.name, "pattern must match the folder"
        assert cp["step"] in STEPS, f"step must be one of {STEPS}"
        for key in ("done", "next", "blocked_on"):
            items = cp.get(key) or []
            assert isinstance(items, list) and all(isinstance(i, str) and i.strip() for i in items), \
                f"{key} must be a list of short sentences"
        if cp["step"] != "done":
            assert cp.get("next"), "next must say what the next session does first (empty only when step is done)"

    def test_branch_and_base(self, folder):
        cp = _load(folder)
        branch, base = cp.get("branch"), cp.get("base")
        if branch is not None:
            m = parse_branch(branch)
            assert m and branch.startswith(f"migrate/{folder.name}/"), \
                f"branch must be migrate/{folder.name}/<YYYYMMDD-HHMM> or null, got {branch!r}"
        assert base == "main" or (str(base).startswith("shared/") and parse_branch(base)), \
            f"base must be main or shared/<topic>/<YYYYMMDD-HHMM>, got {base!r}"
        if cp["step"] not in ("setup", "analyze", "spec") and branch is None:
            warn(f"{folder.name}: step {cp['step']} but no migration branch recorded in checkpoint.yml")

    def test_prs(self, folder):
        prs = _load(folder).get("prs") or {}
        assert isinstance(prs, dict) and set(prs) <= {"shared", "migration"}, "prs has keys shared and migration"
        for k, v in prs.items():
            assert v is None or PR_RX.match(str(v)), f"prs.{k} must be null, a PR number or a GitHub PR URL, got {v!r}"
        cp = _load(folder)
        if cp["step"] in ("pr_review", "done"):
            assert prs.get("migration"), f"step {cp['step']} needs prs.migration"
        if str(cp.get("base", "main")).startswith("shared/") and cp["step"] in ("pr_review", "done"):
            assert prs.get("shared"), "stacked on a shared branch, so prs.shared is needed too"

    def test_updated(self, folder):
        upd = _load(folder).get("updated") or {}
        assert isinstance(upd, dict) and upd.get("by"), "updated.by (session name or person) is required"
        try:
            at = datetime.datetime.strptime(str(upd.get("at")), "%Y-%m-%dT%H:%MZ")
        except ValueError:
            pytest.fail(f"updated.at must be UTC YYYY-MM-DDTHH:MMZ, got {upd.get('at')!r}")
        now = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)
        assert at <= now + datetime.timedelta(minutes=10), "updated.at is in the future"

    def test_step_matches_jobs_csv(self, folder):
        cp, statuses = _load(folder), _statuses(folder.name)
        if cp["step"] == "done":
            assert statuses == {"done"}, f"step done but jobs.csv statuses are {sorted(statuses)}"
        if statuses & {"ready_for_review", "done"}:
            assert cp["step"] in ("pr_review", "done"), \
                f"jobs.csv has {sorted(statuses & {'ready_for_review', 'done'})} but checkpoint step is {cp['step']}"

    def test_blocked_on_components(self, folder):
        cp = _load(folder)
        comps_path = folder / "components.yml"
        open_items = set()
        if comps_path.is_file():
            open_items = {c.get("name") for c in load_yaml(comps_path).get("components") or [] if c.get("status") == "needs_input"}
        listed = set(cp.get("blocked_on") or [])
        missing = sorted(open_items - listed)
        if missing:
            warn(f"{folder.name}: needs_input components not listed in checkpoint blocked_on: {missing}")

    def test_checkpoint_belongs_to_current_branch(self, folder):
        """On a migration branch, its pattern's checkpoint must name that branch and its stack base."""
        branch = current_branch()
        m = parse_branch(branch) if branch else None
        if not (m and branch.startswith("migrate/") and m.group("pattern") == folder.name):
            pytest.skip(f"not on a migrate/{folder.name}/... branch")
        cp = _load(folder)
        assert cp.get("branch") == branch, \
            f"checkpoint.yml branch is {cp.get('branch')!r} but you are on {branch} - update the checkpoint"
        expected_base = stack_base(branch).removeprefix("origin/")
        assert cp.get("base") == expected_base, \
            f"checkpoint.yml base is {cp.get('base')!r} but {branch} is stacked on {expected_base}"
