"""Static checks on migration/<pattern>/{jobs.csv,spec.md,validation.yml}."""
import csv
import re

import pytest

from project import (
    JOBS_CSV, JOBS_CSV_FIELDS, MIGRATION, PATTERN_RX, all_job_keys, inventory_rows, job_files, job_pattern,
    load_yaml, pattern_dirs, warn,
)

STATUSES = {"not_started", "analyzing", "converting", "validating", "ready_for_review", "done", "blocked"}
NEEDS_JOB_FILE = {"converting", "validating", "ready_for_review", "done"}
DATASET_REQUIRED = {"snowflake": ({"table", "query"}, True), "table": ({"table"}, False), "files": ({"path"}, False)}


def test_no_central_inventory():
    """The inventory is split per pattern (migration/pattern_NN/jobs.csv) so owners don't conflict."""
    assert not (MIGRATION / "inventory.csv").exists(), \
        "migration/inventory.csv is replaced by migration/pattern_NN/jobs.csv - move its rows there"


@pytest.mark.parametrize("folder", pattern_dirs(), ids=lambda p: p.name)
def test_jobs_csv_header(folder):
    path = folder / JOBS_CSV
    assert path.is_file(), f"{folder.name}/jobs.csv missing (header: {','.join(JOBS_CSV_FIELDS)})"
    with open(path, newline="") as fh:
        assert next(csv.reader(fh), None) == JOBS_CSV_FIELDS


def test_inventory_rows():
    problems = []
    for r in inventory_rows():
        where = r["source"]
        if r["status"] not in STATUSES:
            problems.append(f"{where}: status '{r['status']}' not in {sorted(STATUSES)}")
        if not r["talend_job"]:
            problems.append(f"{where}: talend_job is required")
        if r["job_key"] and not r["job_key"].startswith(f"{r['pattern']}_"):
            problems.append(f"{where}: job_key '{r['job_key']}' must start with '{r['pattern']}_' (the folder)")
        if "@" not in (r["owner"] or "") and r["status"] != "not_started":
            problems.append(f"{where}: owner email required once work has started")
        if r["status"] == "blocked" and not r["notes"]:
            problems.append(f"{where}: blocked rows need a note")
    assert not problems, problems


def test_inventory_keys_unique():
    """Unique across all patterns, so a Talend job can't be claimed by two families."""
    rows = inventory_rows()
    for field in ("job_key", "talend_job"):
        seen = {}
        for r in rows:
            if r[field]:
                seen.setdefault(r[field], []).append(r["source"])
        dupes = {k: v for k, v in seen.items() if len(v) > 1}
        assert not dupes, f"duplicate {field}: {dupes}"


def test_inventory_matches_job_files():
    rows = inventory_rows()
    listed = {r["job_key"] for r in rows if r["job_key"]}
    defined = all_job_keys()
    missing_files = sorted(r["source"] for r in rows if r["status"] in NEEDS_JOB_FILE and r["job_key"] not in defined)
    assert not missing_files, f"jobs.csv rows without a job file: {missing_files}"
    unlisted = sorted(defined - listed)
    assert not unlisted, f"job files not listed in any migration/pattern_NN/jobs.csv: {unlisted}"
    wrong_folder = sorted(
        f"{f.name} -> listed in {r['pattern']}" for f in job_files() for r in rows
        if r["job_key"] in {k for k in load_yaml(f).get("resources", {}).get("jobs", {})} and job_pattern(f) != r["pattern"]
    )
    assert not wrong_folder, f"job listed in another pattern's jobs.csv: {wrong_folder}"


PATTERN_DIRS = pattern_dirs()


def test_migration_folder_only_holds_patterns():
    """migration/ holds inventory.csv and pattern_NN/ folders only (catches typos and the old patterns/ layer)."""
    stray = sorted(p.name for p in MIGRATION.iterdir() if p.is_dir() and not PATTERN_RX.match(p.name))
    assert not stray, f"unexpected folders in migration/: {stray} (pattern folders are migration/pattern_NN/)"


@pytest.mark.parametrize("folder", PATTERN_DIRS, ids=lambda p: p.name)
class TestPatternFolder:
    def test_spec_decisions(self, folder):
        """spec.md has a `## Decisions` table: | Date | Decision | Why | Decided by |, valid dates, oldest first."""
        spec = folder / "spec.md"
        if not spec.is_file():
            pytest.skip("spec.md missing (reported by test_spec_exists)")
        text = spec.read_text()
        m = re.search(r"^## Decisions\s*$(.*?)(?=^## |\Z)", text, flags=re.M | re.S)
        assert m, "spec.md needs a '## Decisions' section (conventions, Decisions)"
        rows = [l.strip() for l in m.group(1).splitlines() if l.strip().startswith("|")]
        header = [c.strip() for c in rows[0].strip("|").split("|")] if rows else []
        assert header == ["Date", "Decision", "Why", "Decided by"], \
            f"Decisions table header must be | Date | Decision | Why | Decided by |, got {header}"
        dates, problems = [], []
        for row in rows[2:]:  # skip header and separator
            cells = [c.strip() for c in row.strip("|").split("|")]
            if len(cells) != 4 or not all(cells):
                problems.append(f"row needs 4 non-empty cells: {row[:80]}")
                continue
            if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", cells[0]):
                problems.append(f"date must be YYYY-MM-DD: {cells[0]}")
            else:
                dates.append(cells[0])
        assert not problems, problems
        assert dates == sorted(dates), "decisions must be oldest first (append new rows at the end)"

    def test_spec_exists(self, folder):
        spec = folder / "spec.md"
        assert spec.is_file(), "spec.md missing"
        if "TODO" in spec.read_text():
            warn(f"{folder.name}/spec.md still contains TODO")

    def test_talend_exports_present(self, folder):
        if not list((folder / "talend").glob("*.item")):
            warn(f"{folder.name}: no Talend .item exports in talend/")

    def test_validation_config(self, folder):
        path = folder / "validation.yml"
        assert path.is_file(), "validation.yml missing"
        cfg = load_yaml(path)
        assert cfg.get("pattern") == folder.name, "validation.yml pattern must match the folder"
        checks = cfg.get("checks") or []
        assert checks, "validation.yml has no checks"
        names = [c.get("name") for c in checks]
        assert all(names) and len(names) == len(set(names)), f"check names must be set and unique: {names}"
        problems = []
        for c in checks:
            for side in ("expected", "actual"):
                ds = c.get(side) or {}
                kind = ds.get("type")
                if kind not in DATASET_REQUIRED:
                    problems.append(f"{c['name']}.{side}: type must be one of {sorted(DATASET_REQUIRED)}")
                    continue
                fields, one_of = DATASET_REQUIRED[kind]
                present = fields & set(ds)
                if (one_of and len(present) != 1) or (not one_of and present != fields):
                    problems.append(f"{c['name']}.{side}: {kind} needs {'one of ' if one_of else ''}{sorted(fields)}")
                if kind == "snowflake" and not cfg.get("snowflake_secret_scope"):
                    problems.append("snowflake datasets need snowflake_secret_scope")
            if c.get("expected") and c.get("expected") == c.get("actual"):
                problems.append(f"{c['name']}: expected and actual are identical")
            for list_key in ("keys", "ignore_columns"):
                if list_key in c and not (isinstance(c[list_key], list) and all(isinstance(x, str) for x in c[list_key])):
                    problems.append(f"{c['name']}: {list_key} must be a list of column names")
            tol = c.get("numeric_tolerance", 0)
            if not isinstance(tol, (int, float)) or tol < 0:
                problems.append(f"{c['name']}: numeric_tolerance must be >= 0")
            if not c.get("keys"):
                warn(f"{folder.name}/{c['name']}: no keys - full-row diff only")
        assert not problems, problems

    def test_validation_placeholders(self, folder):
        """Snowflake `actual` datasets use ${snowflake_schema}; only placeholders validate_pattern can fill."""
        text = (folder / "validation.yml").read_text()
        unknown = sorted(set(re.findall(r"\$\{([A-Za-z0-9_.]+)\}", text)) - {"snowflake_schema"})
        assert not unknown, f"unknown placeholders {unknown} - only ${{snowflake_schema}} is filled at run time"
        problems = []
        for c in load_yaml(folder / "validation.yml").get("checks") or []:
            actual = c.get("actual") or {}
            if actual.get("type") == "snowflake":
                ref = str(actual.get("table") or actual.get("query") or "")
                if "${snowflake_schema}" not in ref:
                    problems.append(f"{c.get('name')}: actual must reference ${{snowflake_schema}}, got '{ref}'")
        assert not problems, problems

    def test_validation_actual_is_not_prod(self, folder):
        for c in load_yaml(folder / "validation.yml").get("checks") or []:
            table = str((c.get("actual") or {}).get("table", ""))
            assert not re.match(r"(?i)^prod", table), f"{c.get('name')}: actual points at a prod object {table}"
