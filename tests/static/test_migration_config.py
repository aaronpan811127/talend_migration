"""Static checks on migration/<wave>/: folder layout, spec.md, progress/jobs.csv, validation/validation.yml,
learnings/learnings.md (conventions.md, Wave folder)."""
import csv
import re

import pytest

from project import (
    CHECKPOINT, COMPONENTS, JOBS_CSV, JOBS_CSV_FIELDS, LEARNINGS, MIGRATION, PREPARATION_STEPS, PROGRESS_FILES, PROMPT,
    SECRET_RX, SIGN_OFF, SPEC, phase, VALIDATION_YML, WAVE_RX, WAVE_SUBDIRS,
    all_job_keys, inventory_rows, job_files, job_wave, load_yaml, wave_dirs, warn,
)

VALIDATION_ENTRIES = {"validation.yml", "results.md", "reports"}


def _step(folder) -> str:
    path = folder / CHECKPOINT
    return str(load_yaml(path).get("step")) if path.is_file() else "setup"


def _decision_rows(spec_text) -> list:
    """Rows of the spec's ## Decisions table as [date, decision, why, decided_by] (header and separator skipped)."""
    m = re.search(r"^## Decisions\s*$(.*?)(?=^## |\Z)", spec_text, flags=re.M | re.S)
    rows = [l.strip() for l in (m.group(1) if m else "").splitlines() if l.strip().startswith("|")][2:]
    return [cells for cells in ([c.strip() for c in r.strip("|").split("|")] for r in rows) if len(cells) == 4]


LEARNING_RX = re.compile(r"^## (\d{4}-\d{2}-\d{2}) \S", flags=re.M)

STATUSES = {"not_started", "analyzing", "converting", "validating", "ready_for_review", "done", "blocked"}
NEEDS_JOB_FILE = {"converting", "validating", "ready_for_review", "done"}
DATASET_REQUIRED = {"snowflake": ({"table", "query"}, True), "table": ({"table"}, False), "files": ({"path"}, False)}


def test_no_central_inventory():
    """The inventory is split per wave (migration/wave_NN/progress/jobs.csv) so owners don't conflict."""
    assert not (MIGRATION / "inventory.csv").exists(), \
        "migration/inventory.csv is replaced by migration/wave_NN/progress/jobs.csv - move its rows there"


@pytest.mark.parametrize("folder", wave_dirs(), ids=lambda p: p.name)
def test_jobs_csv_header(folder):
    path = folder / JOBS_CSV
    assert path.is_file(), f"{folder.name}/{JOBS_CSV} missing (header: {','.join(JOBS_CSV_FIELDS)})"
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
        if r["job_key"] and not r["job_key"].startswith(f"{r['wave']}_"):
            problems.append(f"{where}: job_key '{r['job_key']}' must start with '{r['wave']}_' (the folder)")
        if "@" not in (r["owner"] or "") and r["status"] != "not_started":
            problems.append(f"{where}: owner email required once work has started")
        if r["status"] == "blocked" and not r["notes"]:
            problems.append(f"{where}: blocked rows need a note")
    assert not problems, problems


def test_inventory_keys_unique():
    """Unique across all waves, so a Talend job can't be claimed by two waves."""
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
    assert not unlisted, f"job files not listed in any migration/wave_NN/progress/jobs.csv: {unlisted}"
    wrong_folder = sorted(
        f"{f.name} -> listed in {r['wave']}" for f in job_files() for r in rows
        if r["job_key"] in {k for k in load_yaml(f).get("resources", {}).get("jobs", {})} and job_wave(f) != r["wave"]
    )
    assert not wrong_folder, f"job listed in another wave's jobs.csv: {wrong_folder}"


WAVE_DIRS = wave_dirs()


def test_migration_folder_only_holds_waves():
    """migration/ holds inventory.csv and wave_NN/ folders only (catches typos and the old waves/ layer)."""
    stray = sorted(p.name for p in MIGRATION.iterdir() if p.is_dir() and not WAVE_RX.match(p.name))
    assert not stray, f"unexpected folders in migration/: {stray} (wave folders are migration/wave_NN/)"


@pytest.mark.parametrize("folder", WAVE_DIRS, ids=lambda p: p.name)
class TestWaveFolder:
    def test_layout(self, folder):
        """spec.md, prompt.md plus inputs/, progress/, validation/, scripts/, learnings/ - nothing else at the wave root."""
        missing = [d for d in WAVE_SUBDIRS if not (folder / d).is_dir()] + [f for f in (SPEC, PROMPT) if not (folder / f).is_file()]
        assert not missing, f"{folder.name} is missing {missing} (conventions, Wave folder)"
        extra = sorted(p.name for p in folder.iterdir() if p.name not in {SPEC, PROMPT, *WAVE_SUBDIRS})
        assert not extra, f"{folder.name}: move {extra} into one of {list(WAVE_SUBDIRS)}"
        stray = sorted(p.name for p in (folder / "progress").iterdir() if p.name not in PROGRESS_FILES)
        assert not stray, f"progress/ holds only {sorted(PROGRESS_FILES)}, found {stray}"
        stray = sorted(p.name for p in (folder / "validation").iterdir() if p.name not in VALIDATION_ENTRIES)
        assert not stray, f"validation/ holds only {sorted(VALIDATION_ENTRIES)}, found {stray}"

    def test_prompt(self, folder):
        """prompt.md: one ```text block under '## Prompt' that names this wave and its lane, points to AGENTS.md,
        asks for the session ids, and says whether the session may deploy."""
        path = folder / PROMPT
        assert path.is_file(), f"{folder.name}/{PROMPT} missing (conventions, Wave folder)"
        text = path.read_text()
        section = re.search(r"^## Prompt\s*$(.*?)(?=^## |\Z)", text, flags=re.M | re.S)
        assert section, "prompt.md needs a '## Prompt' section"
        blocks = re.findall(r"^```text\n(.*?)^```", section.group(1), flags=re.M | re.S)
        assert len(blocks) == 1, f"'## Prompt' must hold exactly one ```text block (the text to paste), found {len(blocks)}"
        prompt, wave = blocks[0], folder.name
        needed = {
            wave: "the wave id",
            f"--var lane={wave}": "its dev lane",
            "AGENTS.md": "the agent instructions",
            "github.com/aaronpan811127/talend_migration": "the repo URL",
            "sys_session_get_info": "recording the session ids at hand-over",
        }
        missing = [f"{k} ({why})" for k, why in needed.items() if k not in prompt]
        assert not missing, f"prompt must mention {missing}"
        others = sorted(set(re.findall(r"\bwave_\d{2}\b", prompt)) - {wave})
        assert not others, f"prompt mentions other waves {others} - copied from another wave?"
        assert re.search(r"(?i)\bdon'?t deploy\b|\bmay deploy\b", prompt), \
            "prompt must say whether the session may deploy ('Don't deploy.' or 'You may deploy ... --var lane=...')"
        assert "--target prod" not in prompt, "never ask a session to use --target prod"
        mode = re.search(r"^Mode: (preparation|conversion)\b", prompt, flags=re.M)
        assert mode, "prompt needs a 'Mode: preparation' or 'Mode: conversion' line (conventions, Phases)"
        step = _step(folder)
        assert mode.group(1) == phase(step), \
            f"prompt says Mode: {mode.group(1)} but checkpoint step '{step}' is the {phase(step)} phase - update prompt.md at the gate"
        assert not SECRET_RX.search(text), "no credentials in prompt.md"

    def test_definition_of_ready(self, folder):
        """From the gate (step ready) on, a wave runs autonomously, so Phase 1 must have closed every question
        (conventions, Definition of ready). Fully checked at step ready; the sign-off and the empty open
        questions stay required afterwards."""
        step = _step(folder)
        if step in PREPARATION_STEPS:
            pytest.skip(f"Phase 1 (step {step}) - the gate is checked at step ready")
        spec = (folder / SPEC).read_text()
        problems = []
        signed = [r for r in _decision_rows(spec) if r[1].lower().startswith(SIGN_OFF.lower()) and "@" in r[3]]
        if not signed:
            problems.append(f"## Decisions needs the sign-off row '{SIGN_OFF}', decided by a person (email)")
        oq = re.search(r"^## Open questions\s*$(.*?)(?=^## |\Z)", spec, flags=re.M | re.S)
        lines = [l.strip(" *-") for l in re.sub(r"<!--.*?-->", "", oq.group(1), flags=re.S).splitlines() if l.strip()] if oq else None
        if lines != ["None"] and lines != ["None."]:
            problems.append(f"spec.md '## Open questions' must say None once the wave is ready, found {lines}")
        if step == "ready":
            comps = (load_yaml(folder / COMPONENTS).get("components") or []) if (folder / COMPONENTS).is_file() else []
            if not comps:
                problems.append("progress/components.yml must list every component before the gate")
            open_items = [c.get("name") for c in comps if c.get("status") == "needs_input"]
            if open_items:
                problems.append(f"components still need input: {open_items} - close them in Phase 1")
            exports = [p.name for p in (folder / "inputs").glob("*.item")]
            for r in [r for r in inventory_rows() if r["wave"] == folder.name]:
                if not any(e.startswith(r["talend_job"]) for e in exports):
                    problems.append(f"no inputs/{r['talend_job']}*.item export for {r['talend_job']}")
                if not r["job_key"] or "@" not in (r["owner"] or ""):
                    problems.append(f"{r['source']}: job_key and owner email are needed before the gate")
        assert not problems, problems

    def test_learnings_log(self, folder):
        """learnings/learnings.md: entries '## YYYY-MM-DD <title>', oldest first, each with a 'Promoted:' line."""
        path = folder / LEARNINGS
        assert path.is_file(), f"{folder.name}/{LEARNINGS} missing"
        text = re.sub(r"<!--.*?-->", "", path.read_text(), flags=re.S)  # the template example is a comment
        entries = re.split(r"^(?=## )", text, flags=re.M)[1:]
        dates, problems = [], []
        for e in entries:
            m = LEARNING_RX.match(e)
            if not m:
                problems.append(f"entry heading must be '## YYYY-MM-DD <title>': {e.splitlines()[0][:60]}")
                continue
            dates.append(m.group(1))
            if not re.search(r"^Promoted: \S", e, flags=re.M):
                problems.append(f"{e.splitlines()[0][3:60]}: add 'Promoted: no' or where it was promoted")
        assert not problems, problems
        assert dates == sorted(dates), "learnings must be oldest first (append new entries at the end)"

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
        spec = folder / SPEC
        assert spec.is_file(), "spec.md missing"
        text = spec.read_text()
        assert re.search(r"^## Why these jobs are one wave\s*$", text, flags=re.M), \
            "spec.md needs '## Why these jobs are one wave' (the grouping rule: pattern, dependencies, ...)"
        assert not re.search(r"^Status:", text, flags=re.M), \
            "spec.md has no Status line - status lives in progress/jobs.csv and progress/checkpoint.yml"
        if "TODO" in text:
            warn(f"{folder.name}/spec.md still contains TODO")

    def test_talend_exports_present(self, folder):
        if not list((folder / "inputs").glob("*.item")):
            warn(f"{folder.name}: no Talend .item exports in inputs/")

    def test_validation_config(self, folder):
        path = folder / VALIDATION_YML
        assert path.is_file(), f"{VALIDATION_YML} missing"
        cfg = load_yaml(path)
        assert cfg.get("wave") == folder.name, "validation.yml wave must match the folder"
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
        """Snowflake `actual` datasets use ${snowflake_schema}; only placeholders validate_wave can fill."""
        text = (folder / VALIDATION_YML).read_text()
        unknown = sorted(set(re.findall(r"\$\{([A-Za-z0-9_.]+)\}", text)) - {"snowflake_schema"})
        assert not unknown, f"unknown placeholders {unknown} - only ${{snowflake_schema}} is filled at run time"
        problems = []
        for c in load_yaml(folder / VALIDATION_YML).get("checks") or []:
            actual = c.get("actual") or {}
            if actual.get("type") == "snowflake":
                ref = str(actual.get("table") or actual.get("query") or "")
                if "${snowflake_schema}" not in ref:
                    problems.append(f"{c.get('name')}: actual must reference ${{snowflake_schema}}, got '{ref}'")
        assert not problems, problems

    def test_validation_actual_is_not_prod(self, folder):
        for c in load_yaml(folder / VALIDATION_YML).get("checks") or []:
            table = str((c.get("actual") or {}).get("table", ""))
            assert not re.match(r"(?i)^prod", table), f"{c.get('name')}: actual points at a prod object {table}"
