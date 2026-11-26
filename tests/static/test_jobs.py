"""Static checks on job definitions (resources/jobs/*.yml). Rules: references/conventions.md."""
import re

import pytest

from project import (
    COMMON_PARAMS, NOTEBOOKS, SECRET_RX, SNAKE_RX, all_job_keys, job_files, job_pattern, job_stem, jobs_in,
    notebook_widgets, rel, resolve_notebook, warn,
)

FILES = job_files()
FILE_RX = re.compile(r"^pattern_\d{2}_[a-z0-9_]+\.job\.yml$")
RUN_JOB_REF_RX = re.compile(r"^\$\{resources\.jobs\.([A-Za-z0-9_]+)\.id\}$")
ALLOWED_TASK_TYPES = {"notebook_task", "run_job_task", "condition_task"}
SNOWFLAKE_OBJECT_PARAM_RX = re.compile(r"^snowflake_.*(table|procedure|proc|sp)s?$|^snowflake_.*(table|procedure)_")
# A qualified reference into a fixed dev schema (e.g. DEV_DB.MIGRATION_DEV.X) bypasses the per-developer schema.
FIXED_SHADOW_RX = re.compile(r"\bMIGRATION_DEV[A-Za-z0-9_]*\.")


def test_there_are_job_files():
    assert FILES, "no job files in resources/jobs/"


def _job(path):
    jobs = jobs_in(path)
    stem = job_stem(path)
    assert list(jobs) == [stem], f"must define exactly one job with key '{stem}', found {list(jobs)}"
    return stem, jobs[stem]


def _notebooks(path, job):
    return [t["notebook_task"]["notebook_path"] for t in job.get("tasks", []) if t.get("notebook_task")]


@pytest.mark.parametrize("path", FILES, ids=rel)
class TestJobFile:
    def test_file_name(self, path):
        assert FILE_RX.match(path.name), "name must be pattern_NN_<talend_job_snake>.job.yml"

    def test_single_job_named_like_file(self, path):
        key, job = _job(path)
        assert job.get("name") == key, f"name '{job.get('name')}' must equal key '{key}'"

    def test_tags(self, path):
        _, job = _job(path)
        tags = job.get("tags") or {}
        assert tags.get("source") == "talend"
        assert tags.get("pattern") == job_pattern(path), f"tag pattern must be {job_pattern(path)}"
        assert tags.get("talend_job"), "tag talend_job (original Talend job name) is required"

    def test_common_parameters(self, path):
        key, job = _job(path)
        params = {p.get("name"): p.get("default") for p in job.get("parameters", [])}
        for name, expected in COMMON_PARAMS.items():
            assert name in params, f"missing common parameter {name}"
            assert params[name] == (key if expected is None else expected), f"{name} must default to {expected or key}"

    def test_parameter_names(self, path):
        _, job = _job(path)
        names = [p.get("name") for p in job.get("parameters", [])]
        assert len(names) == len(set(names)), f"duplicate parameters: {names}"
        assert all(n and SNAKE_RX.match(n) for n in names), f"parameter names must be snake_case: {names}"

    def test_tasks_and_dependencies(self, path):
        _, job = _job(path)
        tasks = job.get("tasks") or []
        assert tasks, "job has no tasks"
        keys = [t.get("task_key") for t in tasks]
        assert len(keys) == len(set(keys)), f"duplicate task_key: {keys}"
        deps = {t["task_key"]: [d["task_key"] for d in t.get("depends_on", [])] for t in tasks}
        unknown = {k: [d for d in v if d not in deps] for k, v in deps.items() if any(d not in deps for d in v)}
        assert not unknown, f"depends_on unknown tasks: {unknown}"
        state = {}

        def visit(k):
            if state.get(k) == 1:
                raise AssertionError(f"dependency cycle through task {k}")
            if state.get(k) != 2:
                state[k] = 1
                for d in deps[k]:
                    visit(d)
                state[k] = 2

        for k in deps:
            visit(k)
        for t in tasks:
            types = ALLOWED_TASK_TYPES.intersection(t) | {k for k in t if k.endswith("_task")}
            assert types and types <= ALLOWED_TASK_TYPES, f"task {t['task_key']}: use one of {sorted(ALLOWED_TASK_TYPES)}"

    def test_notebooks_exist_in_pattern_folder(self, path):
        _, job = _job(path)
        folder = (NOTEBOOKS / job_pattern(path)).resolve()
        for nb in _notebooks(path, job):
            resolved = resolve_notebook(path, nb)
            assert resolved, f"notebook not found: {nb}"
            assert resolved.is_relative_to(folder), f"{nb} must be inside notebooks/{job_pattern(path)}/"

    def test_run_job_tasks_reference_bundle_jobs(self, path):
        _, job = _job(path)
        for t in job.get("tasks", []):
            if "run_job_task" in t:
                m = RUN_JOB_REF_RX.match(str(t["run_job_task"].get("job_id", "")))
                assert m and m.group(1) in all_job_keys(), \
                    f"task {t['task_key']}: job_id must be ${{resources.jobs.<key>.id}} of a job in this bundle"

    def test_every_parameter_has_a_widget(self, path):
        _, job = _job(path)
        widgets = set()
        for nb in _notebooks(path, job):
            if resolve_notebook(path, nb):
                widgets |= notebook_widgets(resolve_notebook(path, nb))
        params = {p["name"] for p in job.get("parameters", [])}
        if _notebooks(path, job):
            assert not (params - widgets), f"parameters no notebook reads: {sorted(params - widgets)}"
            if widgets - params:
                warn(f"{rel(path)}: widgets not set by this job (notebook default used): {sorted(widgets - params)}")

    def test_snowflake_tables_follow_shadow_schema(self, path):
        """Snowflake table and procedure parameters are unqualified, so dev runs use ${var.snowflake_schema}."""
        _, job = _job(path)
        qualified = {
            p["name"]: p.get("default") for p in job.get("parameters", [])
            if SNOWFLAKE_OBJECT_PARAM_RX.match(p["name"]) and "." in str(p.get("default", ""))
        }
        assert not qualified, \
            f"Snowflake table/procedure parameters must be unqualified (schema comes from snowflake_schema): {qualified}"
        assert not FIXED_SHADOW_RX.search(path.read_text()), "hard-coded MIGRATION_DEV schema - use ${var.snowflake_schema}"

    def test_schedules_paused(self, path):
        _, job = _job(path)
        for kind in ("schedule", "trigger", "continuous"):
            block = job.get(kind)
            if block:
                assert block.get("pause_status") == "PAUSED", f"{kind} must be PAUSED until cutover"

    def test_failure_notifications(self, path):
        _, job = _job(path)
        if not ((job.get("email_notifications") or {}).get("on_failure") or job.get("webhook_notifications")):
            warn(f"{rel(path)}: no on_failure notification")

    def test_no_literal_credentials(self, path):
        assert not SECRET_RX.search(path.read_text()), "credentials in job YAML - use a secret scope"


def test_job_keys_unique_across_files():
    keys = [k for f in FILES for k in jobs_in(f)]
    assert len(keys) == len(set(keys)), f"duplicate job keys: {sorted(k for k in keys if keys.count(k) > 1)}"
