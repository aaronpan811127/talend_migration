"""Unit tests for operators.validation (reconciliation). Most need Spark."""
import pytest

from operators.validation import compare_dataframes, load_dataset, substitute_variables

SCHEMA = "order_id INT, amount DOUBLE, status STRING"
ROWS = [(1, 10.0, "A"), (2, 20.0, "B"), (3, 30.0, None)]


def test_substitute_variables_in_nested_config():
    cfg = {"checks": [{"actual": {"type": "snowflake", "table": "DEV_DB.${snowflake_schema}.STG"}, "keys": ["ID"]}],
           "numeric_tolerance": 0}
    out = substitute_variables(cfg, {"snowflake_schema": "MIGRATION_DEV_jane"})
    assert out["checks"][0]["actual"]["table"] == "DEV_DB.MIGRATION_DEV_jane.STG"
    assert out["checks"][0]["keys"] == ["ID"] and out["numeric_tolerance"] == 0
    assert cfg["checks"][0]["actual"]["table"] == "DEV_DB.${snowflake_schema}.STG", "input must not be mutated"


@pytest.mark.parametrize("variables", [None, {}, {"snowflake_schema": ""}, {"other": "x"}])
def test_substitute_variables_missing_value_raises(variables):
    with pytest.raises(ValueError, match="snowflake_schema"):
        substitute_variables({"table": "DEV_DB.${snowflake_schema}.STG"}, variables)


def test_substitute_variables_leaves_plain_strings():
    assert substitute_variables({"filter": "LOAD_DATE = '2026-11-24'"}, None) == {"filter": "LOAD_DATE = '2026-11-24'"}


def test_load_dataset_rejects_unknown_type():
    with pytest.raises(ValueError):
        load_dataset(None, {"type": "ftp"})


def test_load_dataset_snowflake_needs_config():
    with pytest.raises(ValueError):
        load_dataset(None, {"type": "snowflake", "table": "T"}, sf_cfg=None)


@pytest.mark.spark
class TestCompareDataframes:
    def test_identical_data_passes(self, spark):
        e = spark.createDataFrame(ROWS, SCHEMA)
        r = compare_dataframes(e, spark.createDataFrame(ROWS, SCHEMA), keys=["order_id"])
        assert r["passed"], r
        assert r["expected_rows"] == r["actual_rows"] == 3

    def test_column_names_compared_case_insensitively(self, spark):
        e = spark.createDataFrame(ROWS, "ORDER_ID INT, AMOUNT DOUBLE, STATUS STRING")
        r = compare_dataframes(e, spark.createDataFrame(ROWS, SCHEMA), keys=["ORDER_ID"])
        assert r["passed"], r

    def test_value_mismatch_reported(self, spark):
        a_rows = [(1, 10.0, "A"), (2, 21.0, "B"), (3, 30.0, None)]
        r = compare_dataframes(spark.createDataFrame(ROWS, SCHEMA), spark.createDataFrame(a_rows, SCHEMA), keys=["order_id"])
        assert not r["passed"]
        assert r["column_mismatches"] == {"amount": 1}
        assert r["mismatch_sample"][0]["order_id"] == "2"

    def test_null_vs_value_is_a_mismatch(self, spark):
        a_rows = [(1, 10.0, "A"), (2, 20.0, "B"), (3, 30.0, "")]
        r = compare_dataframes(spark.createDataFrame(ROWS, SCHEMA), spark.createDataFrame(a_rows, SCHEMA), keys=["order_id"])
        assert r["column_mismatches"] == {"status": 1}

    def test_missing_and_extra_rows(self, spark):
        a_rows = [(1, 10.0, "A"), (2, 20.0, "B"), (4, 40.0, "D")]
        r = compare_dataframes(spark.createDataFrame(ROWS, SCHEMA), spark.createDataFrame(a_rows, SCHEMA), keys=["order_id"])
        assert not r["passed"]
        assert r["missing_in_actual"] == 1 and r["extra_in_actual"] == 1

    def test_ignore_columns(self, spark):
        a_rows = [(1, 10.0, "X"), (2, 20.0, "Y"), (3, 30.0, "Z")]
        r = compare_dataframes(
            spark.createDataFrame(ROWS, SCHEMA), spark.createDataFrame(a_rows, SCHEMA),
            keys=["order_id"], ignore_columns=["STATUS"],
        )
        assert r["passed"], r

    def test_numeric_tolerance(self, spark):
        a_rows = [(1, 10.001, "A"), (2, 20.0, "B"), (3, 30.0, None)]
        e, a = spark.createDataFrame(ROWS, SCHEMA), spark.createDataFrame(a_rows, SCHEMA)
        assert not compare_dataframes(e, a, keys=["order_id"])["passed"]
        assert compare_dataframes(e, a, keys=["order_id"], numeric_tolerance=0.01)["passed"]

    def test_missing_column_fails(self, spark):
        a = spark.createDataFrame([(r[0], r[1]) for r in ROWS], "order_id INT, amount DOUBLE")
        r = compare_dataframes(spark.createDataFrame(ROWS, SCHEMA), a, keys=["order_id"])
        assert not r["passed"] and r["missing_columns"] == ["status"]

    def test_key_not_in_both_datasets(self, spark):
        e = spark.createDataFrame(ROWS, SCHEMA)
        r = compare_dataframes(e, e, keys=["nope"])
        assert not r["passed"] and "error" in r

    def test_duplicate_keys_counted(self, spark):
        a_rows = ROWS + [(1, 10.0, "A")]
        r = compare_dataframes(spark.createDataFrame(ROWS, SCHEMA), spark.createDataFrame(a_rows, SCHEMA), keys=["order_id"])
        assert r["actual_duplicate_keys"] == 1 and not r["passed"]

    def test_without_keys_uses_multiset_diff(self, spark):
        a_rows = [ROWS[0], ROWS[0], ROWS[2]]
        r = compare_dataframes(spark.createDataFrame(ROWS, SCHEMA), spark.createDataFrame(a_rows, SCHEMA))
        assert not r["passed"]
        assert r["rows_only_in_expected"] == 1 and r["rows_only_in_actual"] == 1
