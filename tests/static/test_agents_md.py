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


# ---------- conventions.md is the single source; AGENTS.md and the skills link to it ----------

CONVENTIONS = ROOT / "skills" / "talend-pattern-migration" / "references" / "conventions.md"
LINK_RX = re.compile(r"conventions\.md#([A-Za-z0-9_-]+)")
ENTRY_POINTS = [AGENTS, ROOT / "skills" / "talend-pattern-migration" / "SKILL.md"]
# Sections every entry point must link, so agents and Genie Code reach the same procedures.
CORE_SECTIONS = {"working-copy", "branches", "checkpoint", "decisions", "resuming-and-handing-over", "prs"}
# Procedure text that belongs only in conventions.md - finding it in an entry point means it was copied back.
CONVENTIONS_ONLY = [
    "git log --oneline origin/main..HEAD",
    "git branch -r --no-merged",
    "gh pr create",
    "Depends on #",
    "never `git add -A`",
]


def _slug(heading: str) -> str:
    """GitHub-style anchor for a markdown heading."""
    return re.sub(r"[^a-z0-9 _-]", "", heading.strip().lower()).replace(" ", "-")


def _anchors(path) -> set:
    anchors, in_code = set(), False
    for line in path.read_text().splitlines():
        if line.startswith("```"):
            in_code = not in_code
        elif not in_code and (m := re.match(r"^#{1,6} (.+)$", line)):
            anchors.add(_slug(m.group(1)))
    return anchors


def _docs():
    files = [AGENTS, ROOT / "README.md", ROOT / "tests" / "README.md", *(ROOT / "skills").rglob("*.md"),
             *(ROOT / "migration").rglob("*.yml"), *(ROOT / ".github").rglob("*.md")]
    return [f for f in files if f.is_file()]


def test_conventions_links_resolve():
    """Every conventions.md#anchor link in docs, skills and pattern files points at a real heading."""
    anchors = _anchors(CONVENTIONS)
    broken = sorted({f"{p.relative_to(ROOT)} -> #{a}" for p in _docs() for a in LINK_RX.findall(p.read_text()) if a not in anchors})
    assert not broken, f"links to conventions.md sections that don't exist (renamed heading?): {broken}"


def test_entry_points_link_core_sections():
    for path in ENTRY_POINTS:
        linked = set(LINK_RX.findall(path.read_text()))
        missing = sorted(CORE_SECTIONS - linked)
        assert not missing, f"{path.relative_to(ROOT)} must link conventions.md sections {missing}"


def test_procedures_not_copied_into_entry_points():
    """Procedures live in conventions.md; AGENTS.md and the skills only link to them."""
    copies = sorted(
        f"{p.relative_to(ROOT)}: {phrase!r}"
        for p in [AGENTS, *(ROOT / "skills").glob("*/SKILL.md")]
        for phrase in CONVENTIONS_ONLY if phrase in p.read_text()
    )
    assert not copies, f"move these back to conventions.md and link to it instead: {copies}"
    conv = CONVENTIONS.read_text()
    assert all(phrase in conv for phrase in CONVENTIONS_ONLY), "conventions.md lost part of a procedure"


def test_slug_matches_github():
    assert _slug("Resuming and handing over") == "resuming-and-handing-over"
    assert _slug("Ownership (avoids merge conflicts)") == "ownership-avoids-merge-conflicts"
    assert _slug("Inventory (`migration/pattern_NN/jobs.csv`)") == "inventory-migrationpattern_nnjobscsv"


def test_names_the_snowflake_schema_parameter():
    assert "snowflake_schema" in COMMON_PARAMS and "snowflake_schema" in AGENTS.read_text()
