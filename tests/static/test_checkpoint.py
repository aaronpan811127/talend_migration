"""Static checks on migration/<pattern>/checkpoint.yml - the pattern's progress, shared by every session
that works on its branch. Rules: .claude/skills/talend-pattern-migration/references/conventions.md#checkpoint
"""
import datetime
import re

import pytest

from project import MAIN, current_branch, inventory_rows, load_yaml, parse_branch, pattern_dirs, shared_base, warn

STEPS = ["setup", "analyze", "spec", "convert", "job_yamls", "tests", "validate", "pr_review", "done"]
FIELDS = {"pattern", "branch", "depends_on", "prs", "step", "updated", "done", "next", "blocked_on", "sessions", "notes"}
REQUIRED = {"pattern", "branch", "depends_on", "prs", "step", "updated", "done", "next", "sessions"}
SESSION_FIELDS = {"id", "by", "at", "summary", "url"}
SESSION_REQUIRED = {"id", "by", "at", "summary"}
TIME_FMT = "%Y-%m-%dT%H:%MZ"
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

    def test_branch_and_depends_on(self, folder):
        cp = _load(folder)
        branch, dep = cp.get("branch"), cp.get("depends_on")
        if branch is not None:
            m = parse_branch(branch)
            assert m and branch.startswith(f"migrate/{folder.name}/"), \
                f"branch must be migrate/{folder.name}/<YYYYMMDD-HHMM> or null, got {branch!r}"
        assert dep is None or (str(dep).startswith("shared/") and parse_branch(dep)), \
            f"depends_on must be null or a shared/<topic>/<YYYYMMDD-HHMM> branch, got {dep!r}"
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
        if cp.get("depends_on") and cp["step"] in ("pr_review", "done"):
            assert prs.get("shared"), "depends on an unmerged shared branch, so prs.shared (its PR) is needed too"

    def test_updated(self, folder):
        upd = _load(folder).get("updated") or {}
        assert isinstance(upd, dict) and upd.get("by"), "updated.by (session name or person) is required"
        try:
            at = datetime.datetime.strptime(str(upd.get("at")), TIME_FMT)
        except ValueError:
            pytest.fail(f"updated.at must be UTC YYYY-MM-DDTHH:MMZ, got {upd.get('at')!r}")
        now = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)
        assert at <= now + datetime.timedelta(minutes=10), "updated.at is in the future"

    def test_sessions(self, folder):
        """Hand-over log: complete entries, oldest first, none later than `updated`."""
        cp = _load(folder)
        sessions = cp.get("sessions")
        assert isinstance(sessions, list) and sessions, "sessions must list at least the session that created the checkpoint"
        times, problems = [], []
        for i, s in enumerate(sessions, 1):
            if not isinstance(s, dict):
                problems.append(f"entry {i} must be a mapping")
                continue
            missing, unknown = SESSION_REQUIRED - set(s), set(s) - SESSION_FIELDS
            if missing or unknown:
                problems.append(f"entry {i}: missing {sorted(missing)} unknown {sorted(unknown)}")
            if any(not str(s.get(k) or "").strip() for k in SESSION_REQUIRED):
                problems.append(f"entry {i}: id, by, at and summary must be non-empty")
            if s.get("url") and not str(s["url"]).startswith("https://"):
                problems.append(f"entry {i}: url must be an https link to the session")
            try:
                times.append(datetime.datetime.strptime(str(s.get("at")), TIME_FMT))
            except ValueError:
                problems.append(f"entry {i}: at must be UTC YYYY-MM-DDTHH:MMZ, got {s.get('at')!r}")
        assert not problems, problems
        assert times == sorted(times), "sessions must be oldest first (append new entries at the end)"
        try:
            updated = datetime.datetime.strptime(str((cp.get("updated") or {}).get("at")), TIME_FMT)
        except ValueError:
            return  # reported by test_updated
        assert times[-1] <= updated, "the last sessions entry is later than updated.at - update both at hand-over"

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
        """On a migration branch, its pattern's checkpoint must name that branch and the shared branch merged into it."""
        branch = current_branch()
        m = parse_branch(branch) if branch else None
        if not (m and branch.startswith("migrate/") and m.group("pattern") == folder.name):
            pytest.skip(f"not on a migrate/{folder.name}/... branch")
        cp = _load(folder)
        assert cp.get("branch") == branch, \
            f"checkpoint.yml branch is {cp.get('branch')!r} but you are on {branch} - update the checkpoint"
        base = shared_base(branch)
        expected = None if base == MAIN else base.removeprefix("origin/")
        assert cp.get("depends_on") == expected, (
            f"checkpoint.yml depends_on is {cp.get('depends_on')!r} but {branch} has "
            + (f"merged in unmerged {expected}" if expected else "no unmerged shared branch merged in (use null)")
        )
