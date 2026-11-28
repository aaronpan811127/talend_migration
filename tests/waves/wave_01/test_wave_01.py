"""Wave-specific tests for wave_01 (owned by the wave owner).

Put tests for this wave here: helper modules kept in notebooks/wave_01/*.py, and
wiring rules specific to this wave that the generic static tests don't cover.
"""
import ast

import pytest

from project import NOTEBOOKS, job_files, jobs_in, python_code, read_notebook

WAVE = "wave_01"
JOBS = [(f, k, j) for f in job_files() if f.name.startswith(f"{WAVE}_") for k, j in jobs_in(f).items()]


@pytest.mark.parametrize("path,key,job", JOBS, ids=[k for _, k, _ in JOBS])
def test_transform_runs_after_extract_load(path, key, job):
    tasks = {t["task_key"]: t for t in job["tasks"]}
    assert {"extract_load", "transform"} <= set(tasks)
    assert [d["task_key"] for d in tasks["transform"].get("depends_on", [])] == ["extract_load"]
    assert tasks["extract_load"]["notebook_task"]["notebook_path"].endswith("01_extract_load.ipynb")
    assert tasks["transform"]["notebook_task"]["notebook_path"].endswith("02_transform.ipynb")


def test_procedure_called_with_bound_job_name():
    """02_transform passes the procedure arguments as a list (bound), not inside the name."""
    cells = read_notebook(NOTEBOOKS / WAVE / "02_transform.ipynb")
    calls = [
        n for c in cells if c["python"] for n in ast.walk(ast.parse(python_code(c)))
        if isinstance(n, ast.Call) and getattr(n.func, "id", None) == "call_procedure"
    ]
    assert len(calls) == 1
    assert isinstance(calls[0].args[2], ast.List), "procedure args must be passed as a list"


def test_stage_load_overwrites():
    """The staging table is reloaded in full each run (Talend tSnowflakeOutputBulkExec with truncate)."""
    code = "\n".join(python_code(c) for c in read_notebook(NOTEBOOKS / WAVE / "01_extract_load.ipynb") if c["python"])
    assert 'mode="overwrite"' in code
