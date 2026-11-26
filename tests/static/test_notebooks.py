"""Static checks on pattern notebooks (notebooks/pattern_NN/*). Rules: references/conventions.md.

Failures block review; `warn(...)` findings show in the pytest warnings summary.
"""
import re

import pytest

from project import (
    COMMON_PARAMS, NOTEBOOKS, PATTERN_RX, SNAKE_RX, WIDGET_RX, all_pattern_notebooks, job_files, job_pattern,
    notebook_python, pattern_notebooks, read_notebook, rel, warn,
)

NBS = all_pattern_notebooks()
FSTRING_SQL_RX = re.compile(r"\b(execute|call_procedure|\.sql)\(\s*f[\"']")
CONCAT_SQL_RX = re.compile(r"\b(execute|\.sql)\(\s*[\"'][^\"']*[\"']\s*(\+|%\s)")
DIRECT_IO_RX = re.compile(
    r"\bspark\.read\b|\.write\s*\.|\.writeStream\b|\.saveAsTable\(|\.insertInto\(|snowflake\.connector|\bjaydebeapi\b|\bpsycopg2?\b"
)
LITERAL_LOCATION_RX = re.compile(r"[\"'](s3a?://[^\"']+|/Volumes/[^\"']+|abfss://[^\"']+|gs://[^\"']+)[\"']")


def test_no_flat_pattern_notebooks():
    flat = sorted(p.name for p in NOTEBOOKS.iterdir() if p.is_file() and PATTERN_RX.match(p.name.split(".")[0]))
    assert not flat, f"pattern notebooks must live in notebooks/pattern_NN/, found {flat}"


@pytest.mark.parametrize("pattern", sorted({job_pattern(f) for f in job_files() if job_pattern(f)}))
def test_pattern_with_jobs_has_notebook_folder(pattern):
    assert pattern_notebooks(pattern), f"jobs exist for {pattern} but notebooks/{pattern}/ has no notebooks"


@pytest.mark.parametrize("path", NBS, ids=rel)
class TestPatternNotebook:
    def test_first_cell_is_markdown_overview(self, path):
        cells = read_notebook(path)
        assert cells and cells[0]["type"] == "markdown", "first cell must be the %md overview"
        assert cells[0]["src"].lstrip().startswith("# "), "overview must start with a '# ' heading"

    def test_code_cells_have_titles(self, path):
        untitled = [i for i, c in enumerate(read_notebook(path), 1) if c["type"] == "code" and not c["title"]]
        if untitled:
            warn(f"{rel(path)}: code cells without a title: {untitled}")

    def test_declares_common_widgets(self, path):
        widgets = set(WIDGET_RX.findall(notebook_python(path)))
        missing = sorted(set(COMMON_PARAMS) - widgets)
        assert not missing, f"missing common widgets {missing}"

    def test_widget_names_are_snake_case(self, path):
        bad = sorted(w for w in WIDGET_RX.findall(notebook_python(path)) if not SNAKE_RX.match(w))
        assert not bad, f"widget names must be snake_case: {bad}"

    def test_imports_operators(self, path):
        assert re.search(r"^\s*from operators(\.\w+)? import", notebook_python(path), re.M), \
            "notebook must use src/operators for I/O and Snowflake calls"

    def test_no_direct_io(self, path):
        hits = sorted({m.group(0) for m in DIRECT_IO_RX.finditer(notebook_python(path))})
        assert not hits, f"ad-hoc I/O in notebook, use operators instead: {hits}"

    def test_sql_uses_bound_parameters(self, path):
        code = notebook_python(path)
        hits = [m.group(0) for m in FSTRING_SQL_RX.finditer(code)] + [m.group(0) for m in CONCAT_SQL_RX.finditer(code)]
        assert not hits, f"SQL built from strings - use bound parameters: {hits}"

    def test_snowflake_config_uses_shadow_schema(self, path):
        """Every SnowflakeConfig is built with schema=p["snowflake_schema"]; no fixed dev schema in code."""
        code = notebook_python(path)
        calls = re.findall(r"SnowflakeConfig\.from_secrets\(([^)]*)\)", code)
        bad = [c for c in calls if "snowflake_schema" not in c]
        assert not bad, f"SnowflakeConfig.from_secrets without schema=p['snowflake_schema']: {bad}"
        assert not re.search(r"\bMIGRATION_DEV[A-Za-z0-9_]*\.", code), "hard-coded MIGRATION_DEV schema - use the snowflake_schema widget"

    def test_no_literal_storage_paths(self, path):
        hits = LITERAL_LOCATION_RX.findall(notebook_python(path))
        if hits:
            warn(f"{rel(path)}: literal storage paths, make them parameters: {hits}")

    def test_spark_connect_friendly(self, path):
        if re.search(r"\bimport pandas\b|\.toPandas\(\)|\.rdd\b|sparkContext|\bsc\.", notebook_python(path)):
            warn(f"{rel(path)}: pandas / toPandas / rdd / sparkContext - not serverless friendly")

    def test_exits_with_summary(self, path):
        if "dbutils.notebook.exit" not in notebook_python(path):
            warn(f"{rel(path)}: does not exit with a run summary (dbutils.notebook.exit)")

    def test_open_review_items(self, path):
        cells = read_notebook(path)
        review = [c["title"] for c in cells if c["title"].startswith("[REVIEW]")]
        todo = [c["title"] or f"cell {i}" for i, c in enumerate(cells, 1) if "TODO" in c["src"]]
        if review or todo:
            warn(f"{rel(path)}: open items - [REVIEW] cells {review}, TODO in {todo}")
