"""Static checks on Python code in src/, tests/ and notebooks/: syntax, imports, credentials."""
import ast

import pytest

from project import (
    NOTEBOOKS, ROOT, SECRET_RX, SKILLS, SRC, notebooks_in, operators_exports, pattern_ids, pattern_modules,
    python_code, read_notebook, rel,
)

PY_FILES = sorted(
    {p for d in (SRC, ROOT / "tests") for p in d.rglob("*.py")}
    | {m for pid in pattern_ids() for m in pattern_modules(pid)}
    | set(SKILLS.glob("*/scripts/**/*.py"))  # reusable skill scripts
)
ALL_NOTEBOOKS = notebooks_in(NOTEBOOKS)


def _imports(tree):
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            yield node.module, [a.name for a in node.names], node.lineno
        elif isinstance(node, ast.Import):
            for a in node.names:
                yield a.name, [], node.lineno


def _check_operator_imports(tree, where):
    exports = operators_exports()
    problems = []
    for module, names, line in _imports(tree):
        if module == "operators":
            missing = [
                n for n in names
                if n != "*" and n not in exports and not (SRC / "operators" / f"{n}.py").is_file()
            ]
            if missing:
                problems.append(f"{where} line {line}: {missing} not exported by operators.__all__")
        elif module.startswith("operators."):
            sub = SRC / (module.replace(".", "/") + ".py")
            if not sub.is_file():
                problems.append(f"{where} line {line}: module {module} does not exist in src/")
    return problems


@pytest.mark.parametrize("path", PY_FILES, ids=rel)
def test_python_file_compiles(path):
    ast.parse(path.read_text(), filename=str(path))


@pytest.mark.parametrize("path", ALL_NOTEBOOKS, ids=rel)
def test_notebook_python_cells_compile(path):
    errors = []
    for i, cell in enumerate(read_notebook(path), 1):
        if cell["python"]:
            try:
                ast.parse(python_code(cell))
            except SyntaxError as exc:
                errors.append(f"cell {i} '{cell['title']}': {exc.msg} (line {exc.lineno})")
    assert not errors, errors


@pytest.mark.parametrize("path", ALL_NOTEBOOKS, ids=rel)
def test_notebook_operator_imports_exist(path):
    problems = []
    for i, cell in enumerate(read_notebook(path), 1):
        if cell["python"]:
            problems += _check_operator_imports(ast.parse(python_code(cell)), f"cell {i}")
    assert not problems, problems


@pytest.mark.parametrize("path", [p for p in PY_FILES if not p.is_relative_to(SRC)], ids=rel)
def test_module_operator_imports_exist(path):
    problems = _check_operator_imports(ast.parse(path.read_text()), rel(path))
    assert not problems, problems


def test_operators_all_is_importable():
    """Every name in operators.__all__ is actually imported or defined in __init__.py."""
    tree = ast.parse((SRC / "operators" / "__init__.py").read_text())
    defined = {a.asname or a.name for n in tree.body if isinstance(n, ast.ImportFrom) for a in n.names}
    defined |= {n.name for n in tree.body if isinstance(n, (ast.FunctionDef, ast.ClassDef))}
    assert operators_exports() <= defined, sorted(operators_exports() - defined)


def test_operators_do_not_use_notebook_globals():
    """src/ must not rely on notebook globals (spark, dbutils, display) - pass them in as arguments."""
    problems = []
    for path in SRC.rglob("*.py"):
        tree = ast.parse(path.read_text())
        bound = {a.arg for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.Lambda)) for a in n.args.args}
        bound |= {t.id for n in ast.walk(tree) if isinstance(n, ast.Assign) for t in n.targets if isinstance(t, ast.Name)}
        bound |= {a.asname or a.name.split(".")[0] for n in ast.walk(tree) if isinstance(n, (ast.Import, ast.ImportFrom)) for a in n.names}
        for n in ast.walk(tree):
            if isinstance(n, ast.Name) and n.id in {"spark", "dbutils", "display"} and n.id not in bound:
                problems.append(f"{rel(path)} line {n.lineno}: uses global {n.id}")
    assert not problems, problems


CRED_FILES = sorted(
    set(PY_FILES) | set(ALL_NOTEBOOKS) | set(ROOT.glob("*.yml")) | set((ROOT / "resources").rglob("*.yml"))
    | set((ROOT / "migration").rglob("*.yml"))
)


@pytest.mark.parametrize("path", [p for p in CRED_FILES if not p.is_relative_to(ROOT / "tests")], ids=rel)
def test_no_hardcoded_credentials(path):
    text = "\n".join(c["src"] for c in read_notebook(path)) if path in ALL_NOTEBOOKS else path.read_text()
    hits = [m.group(0)[:60] for m in SECRET_RX.finditer(text)]
    assert not hits, f"possible hard-coded credentials (use a secret scope): {hits}"
