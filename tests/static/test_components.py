"""Static checks on migration/<wave>/progress/components.yml (status of every Talend component).

Rules: .claude/skills/talend-wave-migration/references/conventions.md#component-status-file
"""
import re

import pytest

from project import COMPONENTS, ROOT, SKILLS, inventory_rows, load_yaml, wave_dirs, wave_notebooks, read_notebook, warn

MAPPINGS = {"standard", "manual", "not_needed", "unsupported"}
STATUSES = {"planned", "resolved", "needs_input", "deferred"}
FIELDS = {"name", "type", "mapping", "implementation", "notebook", "cell", "status", "reason",
          "semantic_deltas", "reviewed_by", "jobs"}
# Inventory statuses from which components.yml is required, and from which nothing may need input.
REQUIRED_FROM = {"converting", "validating", "ready_for_review", "done"}
NO_OPEN_INPUT_FROM = {"ready_for_review", "done"}
MAPPING_DOC = SKILLS / "talend-wave-migration" / "references" / "component-mapping.md"


def _inventory_statuses(wave):
    return {r["status"] for r in inventory_rows() if r["wave"] == wave}


def _documented_types():
    """Talend component names that appear in the first column of component-mapping.md."""
    if not MAPPING_DOC.is_file():
        return set()
    first_cols = [l.split("|")[1] for l in MAPPING_DOC.read_text().splitlines() if l.startswith("| t")]
    return set(re.findall(r"\bt[A-Z][A-Za-z0-9]*\*?", " ".join(first_cols)))


def _is_documented(ctype, documented):
    return ctype in documented or any(d.endswith("*") and ctype.startswith(d[:-1]) for d in documented)


WAVE_DIRS = wave_dirs()


@pytest.mark.parametrize("folder", WAVE_DIRS, ids=lambda p: p.name)
class TestComponents:
    def _load(self, folder):
        path = folder / COMPONENTS
        if not path.is_file():
            statuses = _inventory_statuses(folder.name)
            assert not statuses & REQUIRED_FROM, \
                f"components.yml is required once a job is {sorted(statuses & REQUIRED_FROM)}"
            pytest.skip("no components.yml yet")
        return load_yaml(path)

    def test_structure(self, folder):
        cfg = self._load(folder)
        assert cfg.get("wave") == folder.name, "components.yml wave must match the folder"
        comps = cfg.get("components") or []
        assert comps, "components.yml lists no components"
        names = [c.get("name") for c in comps]
        assert all(names) and len(names) == len(set(names)), f"component names must be set and unique: {names}"
        problems = []
        for c in comps:
            n = c.get("name")
            if set(c) - FIELDS:
                problems.append(f"{n}: unknown fields {sorted(set(c) - FIELDS)}")
            if not c.get("type"):
                problems.append(f"{n}: type (Talend component type) is required")
            if c.get("mapping") not in MAPPINGS:
                problems.append(f"{n}: mapping must be one of {sorted(MAPPINGS)}")
            if c.get("status") not in STATUSES:
                problems.append(f"{n}: status must be one of {sorted(STATUSES)}")
            deltas = c.get("semantic_deltas", [])
            if not (isinstance(deltas, list) and all(isinstance(d, str) and d.strip() for d in deltas)):
                problems.append(f"{n}: semantic_deltas must be a list of sentences")
        assert not problems, problems

    def test_status_rules(self, folder):
        comps = self._load(folder).get("components") or []
        problems = []
        for c in comps:
            n, status, mapping = c.get("name"), c.get("status"), c.get("mapping")
            if status in {"needs_input", "deferred"} and not str(c.get("reason") or "").strip():
                problems.append(f"{n}: {status} needs a reason")
            if status == "resolved" and c.get("reason"):
                warn(f"{folder.name}/{n}: resolved but still has a reason - remove it or reopen")
            if mapping == "unsupported" and status == "resolved":
                problems.append(f"{n}: unsupported components cannot be resolved - use needs_input or deferred")
            if status == "resolved" and mapping != "unsupported" and not str(c.get("implementation") or "").strip():
                problems.append(f"{n}: resolved components need an implementation")
            if status == "planned" and not str(c.get("implementation") or "").strip():
                problems.append(f"{n}: planned components need implementation - the planned approach")
            if status == "planned" and mapping == "unsupported":
                problems.append(f"{n}: unsupported components can't be planned - use needs_input or deferred")
            if mapping == "manual" and status == "resolved" and "@" not in str(c.get("reviewed_by") or ""):
                problems.append(f"{n}: manual mappings need reviewed_by (reviewer email) once resolved")
            if status in {"needs_input", "deferred"}:
                warn(f"{folder.name}/{n}: {status} - {str(c.get('reason', '')).strip()[:100]}")
        assert not problems, problems

    def test_notebook_and_cell_exist(self, folder):
        comps = self._load(folder).get("components") or []
        notebooks = {p.stem: p for p in wave_notebooks(folder.name)}
        problems = []
        for c in comps:
            n, nb = c.get("name"), c.get("notebook")
            if c.get("status") == "resolved" and c.get("mapping") in {"standard", "manual"} and not nb:
                problems.append(f"{n}: resolved {c.get('mapping')} components must name the notebook")
            if nb and nb not in notebooks:
                problems.append(f"{n}: notebook {nb} not in notebooks/{folder.name}/ ({sorted(notebooks)})")
            elif nb and c.get("cell"):
                titles = {cell["title"] for cell in read_notebook(notebooks[nb])}
                if c["cell"] not in titles:
                    problems.append(f"{n}: no cell titled '{c['cell']}' in {nb}")
        assert not problems, problems

    def test_review_cells_are_manual_components(self, folder):
        """Every [REVIEW] cell (translated tJava etc.) must be tracked as a manual component."""
        comps = self._load(folder).get("components") or []
        tracked = {(c.get("notebook"), c.get("cell")) for c in comps if c.get("mapping") == "manual"}
        missing = [
            f"{nb.stem}: {cell['title']}" for nb in wave_notebooks(folder.name)
            for cell in read_notebook(nb) if cell["title"].startswith("[REVIEW]")
            and (nb.stem, cell["title"]) not in tracked
        ]
        assert not missing, f"[REVIEW] cells without a manual component entry: {missing}"

    def test_no_open_input_before_review(self, folder):
        comps = self._load(folder).get("components") or []
        statuses = _inventory_statuses(folder.name)
        if statuses & NO_OPEN_INPUT_FROM:
            open_items = [f"{c['name']} ({c.get('status')})" for c in comps if c.get("status") in {"needs_input", "planned"}]
            assert not open_items, \
                f"jobs are {sorted(statuses & NO_OPEN_INPUT_FROM)} but components still need input or aren't built: {open_items}"

    def test_types_are_in_mapping_reference(self, folder):
        documented = _documented_types()
        comps = self._load(folder).get("components") or []
        unknown = sorted({c["type"] for c in comps if c.get("mapping") == "standard" and c.get("type")
                          and not _is_documented(c["type"], documented)})
        assert not unknown, f"mapping 'standard' but type not in component-mapping.md: {unknown} (use manual, or add a row)"
