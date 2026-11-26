"""Helpers shared by the tests: bundle paths, project rules, notebook and YAML readers."""
import ast
import csv
import json
import re
import warnings
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
NOTEBOOKS = ROOT / "notebooks"
JOBS = ROOT / "resources" / "jobs"
MIGRATION = ROOT / "migration"  # one migration/pattern_NN/ folder per pattern
JOBS_CSV = "jobs.csv"  # per-pattern inventory: migration/pattern_NN/jobs.csv
JOBS_CSV_FIELDS = ["talend_job", "job_key", "owner", "status", "notes"]

PATTERN_RX = re.compile(r"^pattern_\d{2}$")
SNAKE_RX = re.compile(r"^[a-z][a-z0-9_]*$")
# Common job parameters and their required default (None = the job key).
COMMON_PARAMS = {
    "job_name": None,
    "src_path": "${workspace.file_path}/src",
    "catalog": "${var.catalog}",
    "schema": "${var.schema}",
    "snowflake_secret_scope": "${var.snowflake_secret_scope}",
    "snowflake_schema": "${var.snowflake_schema}",
}
WIDGET_RX = re.compile(r"dbutils\.widgets\.(?:text|dropdown|combobox|multiselect)\(\s*[\"']([^\"']+)[\"']")
VAR_RX = re.compile(r"\$\{var\.([A-Za-z0-9_]+)\}")
SECRET_RX = re.compile(r"(?i)\b(password|passwd|pwd|secret|token|private_key)\b\s*[:=]\s*[\"'][^\"'{$<]{3,}[\"']")
SOURCE_HEADER = "# Databricks notebook source"
NON_PYTHON_MAGICS = {"%sql", "%scala", "%r", "%sh", "%fs", "%run", "%md"}


def rel(path) -> str:
    """Path relative to the bundle root, used as pytest ids."""
    return str(Path(path).relative_to(ROOT))


def warn(msg: str) -> None:
    """Non-blocking finding: shown in the pytest warnings summary, does not fail the test."""
    warnings.warn(msg, UserWarning, stacklevel=2)


def load_yaml(path):
    with open(path) as fh:
        return yaml.safe_load(fh) or {}


# ---------- patterns and notebooks ----------

def pattern_dirs() -> list:
    """migration/pattern_NN/ folders."""
    if not MIGRATION.is_dir():
        return []
    return sorted(p for p in MIGRATION.iterdir() if p.is_dir() and PATTERN_RX.match(p.name))


def inventory_rows() -> list:
    """All rows of every migration/pattern_NN/jobs.csv, each with `pattern` and `source` (file:line) added."""
    rows = []
    for folder in pattern_dirs():
        path = folder / JOBS_CSV
        if path.is_file():
            with open(path, newline="") as fh:
                for i, r in enumerate(csv.DictReader(fh), 2):
                    rows.append({**r, "pattern": folder.name, "source": f"{rel(path)}:{i}"})
    return rows


def pattern_ids() -> list:
    """Pattern ids that have a notebook folder, a migration folder or a job file."""
    ids = set()
    for base in (NOTEBOOKS, MIGRATION):
        if base.is_dir():
            ids |= {p.name for p in base.iterdir() if p.is_dir() and PATTERN_RX.match(p.name)}
    ids |= {job_pattern(f) for f in job_files() if job_pattern(f)}
    return sorted(ids)


def is_notebook(path: Path) -> bool:
    if path.suffix == ".ipynb":
        return True
    if path.suffix == ".py":
        with open(path) as fh:
            return fh.readline().strip() == SOURCE_HEADER
    return False


def notebooks_in(folder: Path) -> list:
    return sorted(p for p in folder.rglob("*") if p.is_file() and is_notebook(p)) if folder.is_dir() else []


def pattern_notebooks(pattern: str) -> list:
    return notebooks_in(NOTEBOOKS / pattern)


def all_pattern_notebooks() -> list:
    return [nb for pid in pattern_ids() for nb in pattern_notebooks(pid)]


def pattern_modules(pattern: str) -> list:
    """Plain Python helper modules (not notebooks) kept next to a pattern's notebooks."""
    folder = NOTEBOOKS / pattern
    return sorted(p for p in folder.rglob("*.py") if not is_notebook(p)) if folder.is_dir() else []


def _cell(cell_type: str, src: str, title: str, default_lang: str) -> dict:
    stripped = src.lstrip()
    if cell_type == "code" and stripped.startswith("%md"):
        cell_type, src = "markdown", stripped[3:].lstrip("\n")
        stripped = src.lstrip()
    first = stripped.split(None, 1)[0].lower() if stripped else ""
    python = cell_type == "code" and default_lang == "python" and first not in NON_PYTHON_MAGICS
    return {"type": cell_type, "src": src, "title": title or "", "python": python}


def read_notebook(path) -> list:
    """Cells of a notebook (.ipynb, or .py in Databricks source format) as dicts:
    type ('code' | 'markdown'), src, title, python (True for Python code cells)."""
    path = Path(path)
    if path.suffix == ".ipynb":
        nb = json.loads(path.read_text())
        nb_meta = (nb.get("metadata") or {}).get("application/vnd.databricks.v1+notebook") or {}
        lang = nb_meta.get("language", "python")
        cells = []
        for c in nb.get("cells", []):
            src = "".join(c.get("source", [])) if isinstance(c.get("source"), list) else c.get("source", "")
            meta = (c.get("metadata") or {}).get("application/vnd.databricks.v1+cell") or {}
            cells.append(_cell(c.get("cell_type", "code"), src, meta.get("title", ""), lang))
        return cells
    text = path.read_text()
    body = text.split("\n", 1)[1] if text.startswith(SOURCE_HEADER) else text
    cells = []
    for chunk in re.split(r"\n# COMMAND ----------\n", body):
        lines = chunk.strip("\n").splitlines()
        title = ""
        if lines and lines[0].startswith("# DBTITLE"):
            title = lines[0].split(",", 1)[-1].strip()
            lines = lines[1:]
        if lines and all(l.startswith("# MAGIC") for l in lines if l.strip()):
            lines = [l[8:] if l.startswith("# MAGIC ") else l[7:] for l in lines]
        cells.append(_cell("code", "\n".join(lines), title, "python"))
    return cells


def python_code(cell: dict) -> str:
    """Python source of a cell with magic (%) and shell (!) lines blanked, ready for ast.parse."""
    return "\n".join("" if l.lstrip().startswith(("%", "!")) else l for l in cell["src"].splitlines())


def notebook_python(path) -> str:
    return "\n".join(python_code(c) for c in read_notebook(path) if c["python"])


def notebook_widgets(path) -> set:
    return set(WIDGET_RX.findall(notebook_python(path)))


def operators_exports() -> set:
    """Names in src/operators/__init__.py __all__."""
    tree = ast.parse((SRC / "operators" / "__init__.py").read_text())
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(getattr(t, "id", None) == "__all__" for t in node.targets):
            return set(ast.literal_eval(node.value))
    return set()


# ---------- jobs ----------

def job_files() -> list:
    return sorted(JOBS.glob("*.yml")) if JOBS.is_dir() else []


def job_stem(path: Path) -> str:
    name = path.name
    return name[: -len(".job.yml")] if name.endswith(".job.yml") else path.stem


def job_pattern(path: Path):
    m = re.match(r"^(pattern_\d{2})_", path.name)
    return m.group(1) if m else None


def jobs_in(path: Path) -> dict:
    return ((load_yaml(path).get("resources") or {}).get("jobs")) or {}


def all_job_keys() -> set:
    return {k for f in job_files() for k in jobs_in(f)}


def resolve_notebook(job_file: Path, notebook_path: str):
    """Resolve a notebook_task.notebook_path (relative to the YAML file) to an existing file, else None."""
    p = (job_file.parent / notebook_path).resolve()
    candidates = [p] if p.suffix else [p.with_suffix(".ipynb"), p.with_suffix(".py")]
    return next((c for c in candidates if c.is_file()), None)
