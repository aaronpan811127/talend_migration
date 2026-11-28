"""Reusable scripts live only in .claude/skills/<skill>/scripts/ and follow the Reusable scripts rules in
conventions.md: docstring with Usage, argparse CLI whose --help works, listed in the skill's ## Scripts section,
and (Python) a unit test in tests/unit/scripts/. Shared-branch-only is enforced by test_git_ownership.py.
"""
import ast
import os
import re
import subprocess
import sys

import pytest

from project import MIGRATION, NOTEBOOKS, ROOT, SKILLS, SRC, WAVE_RX, rel, warn

SCRIPT_SUFFIXES = {".py", ".sh"}
# Code may also live in the operator package, the tests and wave notebooks / helper modules.
ALLOWED_ROOTS = [SRC, ROOT / "tests", NOTEBOOKS]
IGNORED_PARTS = {".git", ".databricks", "__pycache__", ".venv", "venv", ".pytest_cache"}
UNIT_TESTS = ROOT / "tests" / "unit" / "scripts"


def _code_files():
    for p in ROOT.rglob("*"):
        if p.suffix in SCRIPT_SUFFIXES and p.is_file() and not set(p.relative_to(ROOT).parts) & IGNORED_PARTS:
            yield p


def _is_skill_script(p) -> bool:
    """True for .claude/skills/<skill>/scripts/<...>."""
    if not p.is_relative_to(SKILLS):
        return False
    parts = p.relative_to(SKILLS).parts
    return len(parts) >= 3 and parts[1] == "scripts"


def _is_wave_script(p) -> bool:
    """True for migration/wave_NN/scripts/<...> - scripts only this wave needs."""
    if not p.is_relative_to(MIGRATION):
        return False
    parts = p.relative_to(MIGRATION).parts
    return len(parts) >= 3 and WAVE_RX.match(parts[0]) is not None and parts[1] == "scripts"


def skill_scripts() -> list:
    return sorted(p for p in _code_files() if _is_skill_script(p))


def wave_scripts() -> list:
    return sorted(p for p in _code_files() if _is_wave_script(p))


def _skill_of(path):
    return SKILLS / path.relative_to(SKILLS).parts[0]


def _scripts_section(skill_dir) -> str:
    text = (skill_dir / "SKILL.md").read_text()
    m = re.search(r"^## Scripts\s*$(.*?)(?=^## |\Z)", text, flags=re.M | re.S)
    return m.group(1) if m else ""


def test_scripts_only_in_scripts_folders():
    stray = sorted(
        rel(p) for p in _code_files()
        if not (_is_skill_script(p) or _is_wave_script(p)) and not any(p.is_relative_to(r) for r in ALLOWED_ROOTS)
    )
    assert not stray, (
        "scripts belong in .claude/skills/<skill>/scripts/ (reusable) or migration/wave_NN/scripts/ "
        f"(this wave only) - conventions.md, Reusable scripts; found: {stray}"
    )


@pytest.mark.parametrize("skill", sorted(p.parent for p in SKILLS.glob("*/SKILL.md")), ids=lambda p: p.name)
def test_skill_has_scripts_folder_and_section(skill):
    assert (skill / "scripts").is_dir(), f"{skill.name} needs a scripts/ folder"
    assert _scripts_section(skill), f"{skill.name}/SKILL.md needs a '## Scripts' section listing its scripts"


class _CliChecks:
    """Checks every script gets, reusable or wave-only."""

    def test_docstring_and_cli(self, path):
        if path.suffix != ".py":
            first = path.read_text().splitlines()[:1]
            assert first and first[0].startswith("#!"), "shell scripts start with a shebang"
            assert "set -e" in path.read_text(), "shell scripts use set -e (or set -euo pipefail)"
            return
        tree = ast.parse(path.read_text())
        doc = ast.get_docstring(tree) or ""
        assert "Usage" in doc, "module docstring must say what the script does, its inputs/outputs and a Usage: example"
        imports = {a.name for n in ast.walk(tree) if isinstance(n, (ast.Import, ast.ImportFrom))
                   for a in n.names} | {n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)}
        assert "argparse" in imports, "use argparse so --help documents the arguments"
        assert re.search(r"^if __name__ == [\"']__main__[\"']:", path.read_text(), flags=re.M), \
            "guard the entry point with if __name__ == '__main__':"

    def test_help_runs(self, path):
        cmd = [sys.executable, str(path), "--help"] if path.suffix == ".py" else ["sh", str(path), "--help"]
        r = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, timeout=60,
                           env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"})
        assert r.returncode == 0 and "usage" in (r.stdout + r.stderr).lower(), \
            f"--help must exit 0 and print usage; got exit {r.returncode}: {(r.stderr or r.stdout)[-300:]}"

@pytest.mark.parametrize("path", skill_scripts(), ids=rel)
class TestSkillScript(_CliChecks):
    def test_listed_in_skill(self, path):
        assert path.name in _scripts_section(_skill_of(path)), \
            f"list {path.name} in the '## Scripts' section of {_skill_of(path).name}/SKILL.md"

    def test_has_unit_test(self, path):
        if path.suffix == ".py":
            expected = UNIT_TESTS / f"test_{path.stem}.py"
            assert expected.is_file(), f"add a unit test: {rel(expected)}"


@pytest.mark.parametrize("path", wave_scripts(), ids=rel)
class TestWaveScript(_CliChecks):
    def test_has_unit_test_recommended(self, path):
        wave = path.relative_to(MIGRATION).parts[0]
        tests = ROOT / "tests" / "waves" / wave
        if path.suffix == ".py" and not any(path.stem in t.read_text() for t in tests.glob("test_*.py")):
            warn(f"{rel(path)}: no test in tests/waves/{wave}/ mentions it")
