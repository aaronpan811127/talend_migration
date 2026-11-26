"""Keep AGENTS.md (instructions for non-Genie agent harnesses) in sync with the repo."""
import re

from project import COMMON_PARAMS, ROOT, pattern_dirs

AGENTS = ROOT / "AGENTS.md"
# Backticked repo paths, e.g. `skills/.../SKILL.md` or `notebooks/pattern_NN/`. pattern_NN is a placeholder.
PATH_RX = re.compile(r"`((?:skills|src|tests|notebooks|resources|migration)/[^`\s*<>]*|[A-Za-z_-]+\.(?:md|ini|txt|yml))`")


def test_agents_md_exists():
    assert AGENTS.is_file()


def test_claude_md_imports_agents_md():
    """Claude Code reads CLAUDE.md, not AGENTS.md."""
    assert "@AGENTS.md" in (ROOT / "CLAUDE.md").read_text()


# Per-pattern files named without a folder (e.g. `spec.md`); validation_results.md is created during validation.
PATTERN_FILES_OPTIONAL = {"validation_results.md"}


def _exists(ref: str) -> bool:
    ref = ref.rstrip("/")
    if "pattern_NN" in ref:  # placeholder: check the fixed part, e.g. notebooks/
        ref = ref.split("pattern_NN")[0].rstrip("/")
    if (ROOT / ref).exists() or (ROOT / f"{ref}.ipynb").exists():
        return True
    if "/" not in ref:  # bare file name: a root file, or a file in every pattern folder
        return ref in PATTERN_FILES_OPTIONAL or (bool(pattern_dirs()) and all((d / ref).exists() for d in pattern_dirs()))
    return False


def test_referenced_paths_exist():
    missing = sorted(r for r in set(PATH_RX.findall(AGENTS.read_text())) if not _exists(r))
    assert not missing, f"AGENTS.md references paths that don't exist: {missing}"


def test_mentions_every_skill():
    text = AGENTS.read_text()
    skills = sorted(p.parent.name for p in (ROOT / "skills").glob("*/SKILL.md"))
    assert skills and all(f"skills/{s}/SKILL.md" in text for s in skills), f"AGENTS.md must point to every skill: {skills}"


def test_names_the_snowflake_schema_parameter():
    assert "snowflake_schema" in COMMON_PARAMS and "snowflake_schema" in AGENTS.read_text()
