"""Keep AGENTS.md (the entry point for coding agents) in sync with the repo."""
import re
from pathlib import Path

from project import COMMON_PARAMS, CONVENTIONS, ROOT, SKILLS, wave_dirs

AGENTS = ROOT / "AGENTS.md"
# Backticked repo paths, e.g. `.claude/skills/.../SKILL.md` or `notebooks/wave_NN/`. wave_NN is a placeholder.
PATH_RX = re.compile(r"`((?:\.claude/skills|src|tests|notebooks|resources|migration)/[^`\s*<>]*|[A-Za-z_-]+\.(?:md|ini|txt|yml))`")


def test_agents_md_exists():
    assert AGENTS.is_file()


def test_claude_md_imports_agents_md():
    """Claude Code reads CLAUDE.md, not AGENTS.md."""
    assert "@AGENTS.md" in (ROOT / "CLAUDE.md").read_text()


# Per-wave files named without a folder (e.g. `spec.md`); results.md is created during validation.
WAVE_FILES_OPTIONAL = {"results.md"}


def _exists(ref: str) -> bool:
    ref = ref.rstrip("/")
    if ref.startswith("migration/wave_NN/"):  # a file inside a wave folder: check it in every wave
        inner = ref[len("migration/wave_NN/"):]
        return Path(inner).name in WAVE_FILES_OPTIONAL or (
            bool(wave_dirs()) and all((d / inner).exists() for d in wave_dirs()))
    if "wave_NN" in ref:  # placeholder: check the fixed part, e.g. notebooks/
        ref = ref.split("wave_NN")[0].rstrip("/")
    if (ROOT / ref).exists() or (ROOT / f"{ref}.ipynb").exists():
        return True
    if "/" not in ref:  # bare file name: a root file, or a file somewhere in every wave folder
        return ref in WAVE_FILES_OPTIONAL or (bool(wave_dirs()) and all(any(d.rglob(ref)) for d in wave_dirs()))
    return False


def test_referenced_paths_exist():
    missing = sorted(r for r in set(PATH_RX.findall(AGENTS.read_text())) if not _exists(r))
    assert not missing, f"AGENTS.md references paths that don't exist: {missing}"


def test_mentions_every_skill():
    text = AGENTS.read_text()
    skills = sorted(p.parent.name for p in SKILLS.glob("*/SKILL.md"))
    assert skills and all(f".claude/skills/{s}/SKILL.md" in text for s in skills), f"AGENTS.md must point to every skill: {skills}"


# ---------- skills stay discoverable by skill loaders (Claude Code, Omnigent Claude sessions) ----------

FRONTMATTER_RX = re.compile(r"\A---\n(.*?)\n---\n", re.S)
MD_LINK_RX = re.compile(r"\]\(([^)#\s]+)(?:#[^)]*)?\)")


def test_skills_live_in_agents_skills():
    """Skills are in .claude/skills/ - where Claude harnesses discover them - and nowhere else."""
    for old in ("skills", ".agents/skills"):
        assert not (ROOT / old).exists(), f"skills belong in .claude/skills/, not {old}/ (only one copy, or they drift)"
    assert sorted(p.parent.name for p in SKILLS.glob("*/SKILL.md")), "no skills found in .claude/skills/"
    assert not SKILLS.is_symlink(), ".claude/skills must be a real folder (Omnigent rejects a symlinked skills root)"


def test_skill_frontmatter():
    """Each SKILL.md has name (= folder name, [a-z0-9-]+, as loaders require) and a description."""
    problems = []
    for path in sorted(SKILLS.glob("*/SKILL.md")):
        m = FRONTMATTER_RX.match(path.read_text())
        meta = dict(re.findall(r"^([a-z_-]+):\s*(.+)$", m.group(1), flags=re.M)) if m else {}
        folder = path.parent.name
        if meta.get("name") != folder:
            problems.append(f"{folder}: frontmatter name {meta.get('name')!r} must equal the folder name")
        if not re.fullmatch(r"[a-z0-9-]+", folder):
            problems.append(f"{folder}: skill names must match [a-z0-9-]+")
        if len(meta.get("description", "")) < 40:
            problems.append(f"{folder}: needs a description (it is what loaders show to pick the skill)")
    assert not problems, problems


def test_skill_links_stay_inside_skills():
    """Skill loaders only read files inside a skill, so a SKILL.md may link its own files or another skill's -
    never other repo files."""
    outside = []
    for path in sorted(SKILLS.rglob("*.md")):
        for target in MD_LINK_RX.findall(path.read_text()):
            if "://" in target:
                continue
            resolved = (path.parent / target).resolve()
            if not resolved.is_relative_to(SKILLS.resolve()):
                outside.append(f"{path.relative_to(ROOT)} -> {target}")
    assert not outside, f"links from skills to files outside .claude/skills/ (loaders can't read them): {outside}"


# ---------- conventions.md is the single source; AGENTS.md and the skills link to it ----------

LINK_RX = re.compile(r"conventions\.md#([A-Za-z0-9_-]+)")
ENTRY_POINTS = [SKILLS / "talend-wave-migration" / "SKILL.md"]
# Sections the migration skill must link, so every harness reaches the same procedures.
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
    files = [AGENTS, ROOT / "README.md", ROOT / "tests" / "README.md", *SKILLS.rglob("*.md"),
             *(ROOT / "migration").rglob("*.yml"), *(ROOT / ".github").rglob("*.md")]
    return [f for f in files if f.is_file()]


def test_conventions_links_resolve():
    """Every conventions.md#anchor link in docs, skills and wave files points at a real heading."""
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
        for p in [AGENTS, *SKILLS.glob("*/SKILL.md")]
        for phrase in CONVENTIONS_ONLY if phrase in p.read_text()
    )
    assert not copies, f"move these back to conventions.md and link to it instead: {copies}"
    conv = CONVENTIONS.read_text()
    assert all(phrase in conv for phrase in CONVENTIONS_ONLY), "conventions.md lost part of a procedure"


def test_slug_matches_github():
    assert _slug("Resuming and handing over") == "resuming-and-handing-over"
    assert _slug("Ownership (avoids merge conflicts)") == "ownership-avoids-merge-conflicts"
    assert _slug("Inventory (`migration/wave_NN/progress/jobs.csv`)") == "inventory-migrationwave_nnprogressjobscsv"


def test_names_the_snowflake_schema_parameter():
    assert "snowflake_schema" in COMMON_PARAMS and "snowflake_schema" in CONVENTIONS.read_text()


# AGENTS.md only says how to load the skills and map their tools; migration instructions live in the skills.
AGENTS_SECTIONS = {"Load the skills", "Tool mapping"}
AGENTS_MAX_WORDS = 450


def test_agents_md_is_a_thin_entry_point():
    text = AGENTS.read_text()
    sections = set(re.findall(r"^## (.+)$", text, flags=re.M))
    assert sections <= AGENTS_SECTIONS, (
        f"AGENTS.md has sections {sorted(sections - AGENTS_SECTIONS)} - migration instructions belong in the "
        "skills (conventions.md); AGENTS.md only loads the skills and maps tools"
    )
    words = len(text.split())
    assert words <= AGENTS_MAX_WORDS, f"AGENTS.md has {words} words (max {AGENTS_MAX_WORDS}) - move instructions to the skills"
    assert "conventions.md" in text, "AGENTS.md must point to conventions.md"
