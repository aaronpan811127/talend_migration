"""Static checks on databricks.yml and variable references across the bundle."""
import pytest

from project import ROOT, VAR_RX, load_yaml, rel, warn

BUNDLE = load_yaml(ROOT / "databricks.yml")
VARIABLES = BUNDLE.get("variables") or {}
TARGETS = BUNDLE.get("targets") or {}
REQUIRED_VARIABLES = {"catalog", "schema", "landing_root", "lane", "snowflake_secret_scope", "snowflake_schema", "notification_email"}
LANE = "${var.lane}"
YML_FILES = sorted({ROOT / "databricks.yml"} | set((ROOT / "resources").rglob("*.yml")))


def test_bundle_name():
    assert (BUNDLE.get("bundle") or {}).get("name") == "talend_migration"


def test_includes_job_resources():
    assert "resources/jobs/*.yml" in (BUNDLE.get("include") or [])


def test_required_variables_declared_with_descriptions():
    assert REQUIRED_VARIABLES <= set(VARIABLES), sorted(REQUIRED_VARIABLES - set(VARIABLES))
    undocumented = [k for k, v in VARIABLES.items() if not (v or {}).get("description")]
    assert not undocumented, f"variables without description: {undocumented}"


def test_dev_target_is_default_development():
    dev = TARGETS.get("dev") or {}
    assert dev.get("mode") == "development" and dev.get("default") is True


def test_prod_target():
    prod = TARGETS.get("prod") or {}
    assert prod.get("mode") == "production"
    assert (prod.get("workspace") or {}).get("root_path"), "prod needs a shared workspace.root_path"
    pv = prod.get("variables") or {}
    assert pv.get("snowflake_secret_scope") and pv["snowflake_secret_scope"] != VARIABLES["snowflake_secret_scope"].get("default"), \
        "prod must override snowflake_secret_scope (not use the dev scope)"


def test_dev_snowflake_schema_is_per_developer_and_lane():
    """Parallel developers and parallel agents (lanes) must not share a Snowflake schema in dev."""
    default = str((VARIABLES.get("snowflake_schema") or {}).get("default", ""))
    dev_value = str(((TARGETS.get("dev") or {}).get("variables") or {}).get("snowflake_schema", default))
    assert "${workspace.current_user." in dev_value, f"dev snowflake_schema must include the current user, got '{dev_value}'"
    assert LANE in dev_value, f"dev snowflake_schema must include {LANE}, got '{dev_value}'"


def test_lane_default_is_main():
    assert str((VARIABLES.get("lane") or {}).get("default")) == "main"


def test_dev_deploys_are_isolated_per_lane():
    """Each lane gets its own deploy folder (and so its own deployment lock and state) and job-name prefix."""
    dev = TARGETS.get("dev") or {}
    root_path = str((dev.get("workspace") or {}).get("root_path", ""))
    assert LANE in root_path, f"dev workspace.root_path must include {LANE}, got '{root_path}'"
    prefix = str((dev.get("presets") or {}).get("name_prefix", ""))
    assert LANE in prefix and "${workspace.current_user." in prefix, \
        f"dev presets.name_prefix must include the user and {LANE}, got '{prefix}'"


def test_prod_does_not_use_lane():
    prod = TARGETS.get("prod") or {}
    assert "lane" not in str(prod), "prod must not depend on the dev lane"


def test_prod_sets_its_own_snowflake_schema():
    pv = ((TARGETS.get("prod") or {}).get("variables") or {})
    assert pv.get("snowflake_schema") and "current_user" not in str(pv["snowflake_schema"]), \
        "prod must set a fixed snowflake_schema (not the per-developer default)"


@pytest.mark.parametrize("name,target", sorted(TARGETS.items()))
def test_target_variables_are_declared(name, target):
    unknown = set((target or {}).get("variables") or {}) - set(VARIABLES)
    assert not unknown, f"target {name} sets undeclared variables {sorted(unknown)}"


@pytest.mark.parametrize("path", YML_FILES, ids=rel)
def test_variable_references_are_declared(path):
    used = set(VAR_RX.findall(path.read_text()))
    assert used <= set(VARIABLES), f"undeclared variables: {sorted(used - set(VARIABLES))}"


def test_unused_variables():
    used = {v for p in YML_FILES for v in VAR_RX.findall(p.read_text())}
    if set(VARIABLES) - used:
        warn(f"declared but unused variables: {sorted(set(VARIABLES) - used)}")
