"""Unit tests for operators.readers / operators.writers using recording fakes (no Spark needed)."""
import types

import pytest

from operators.config import JdbcConfig, SnowflakeConfig
from operators.readers import read_files, read_jdbc, read_snowflake, read_table
from operators.writers import write_delta, write_files, write_jdbc, write_snowflake

SF = SnowflakeConfig(account="acc", user="u", password="p", role="r", warehouse="wh", database="db")
JDBC = JdbcConfig(url="jdbc:postgresql://h/db", user="u", password="p", driver="org.postgresql.Driver")


class Recorder:
    """Stands in for DataFrameReader / DataFrameWriter: records every chained call."""

    def __init__(self):
        self.calls = []

    def __getattr__(self, name):
        if name.startswith("__"):
            raise AttributeError(name)

        def method(*args, **kwargs):
            self.calls.append((name, args, kwargs))
            return self

        return method

    def args(self, name):
        return [a for n, a, _ in self.calls if n == name]

    def recorded_options(self):
        """All option(...) / options(...) values merged, in call order."""
        out = {}
        for n, a, kw in self.calls:
            if n == "option":
                out[a[0]] = a[1]
            elif n == "options":
                out.update(kw)
        return out


def fake_spark():
    return types.SimpleNamespace(read=Recorder())


def fake_df():
    return types.SimpleNamespace(write=Recorder())


# ---------- readers ----------

def test_read_files_csv_defaults_to_header():
    spark = fake_spark()
    read_files(spark, "s3://b/in/", fmt="csv")
    assert spark.read.args("format") == [("csv",)]
    assert spark.read.recorded_options() == {"header": "true"}
    assert spark.read.args("load") == [("s3://b/in/",)]


def test_read_files_options_override_defaults_and_schema_applied():
    spark = fake_spark()
    read_files(spark, "/Volumes/c/s/v/in", fmt="csv", options={"header": "false", "sep": ";"}, schema="id INT")
    assert spark.read.recorded_options() == {"header": "false", "sep": ";"}
    assert spark.read.args("schema") == [("id INT",)]


def test_read_files_non_csv_has_no_header_default():
    spark = fake_spark()
    read_files(spark, "s3://b/in/", fmt="parquet")
    assert spark.read.recorded_options() == {}
    assert spark.read.args("schema") == []


def test_read_table():
    spark = fake_spark()
    read_table(spark, "c.s.t")
    assert spark.read.args("table") == [("c.s.t",)]


@pytest.mark.parametrize("kwargs", [{}, {"table": "T", "query": "select 1"}])
def test_read_jdbc_requires_exactly_one_of_table_or_query(kwargs):
    with pytest.raises(ValueError):
        read_jdbc(None, JDBC, **kwargs)


@pytest.mark.parametrize("kwargs", [{}, {"table": "T", "query": "select 1"}])
def test_read_snowflake_requires_exactly_one_of_table_or_query(kwargs):
    with pytest.raises(ValueError):
        read_snowflake(None, SF, **kwargs)


def test_read_jdbc_table_and_driver():
    spark = fake_spark()
    read_jdbc(spark, JDBC, table="public.orders", options={"fetchsize": "1000"})
    opts = spark.read.recorded_options()
    assert opts["url"] == JDBC.url and opts["dbtable"] == "public.orders"
    assert opts["driver"] == "org.postgresql.Driver" and opts["fetchsize"] == "1000"
    assert "query" not in opts


def test_read_snowflake_query_uses_config_options():
    spark = fake_spark()
    read_snowflake(spark, SF, query="select 1")
    opts = spark.read.recorded_options()
    assert spark.read.args("format") == [("snowflake",)]
    assert opts["query"] == "select 1" and "dbtable" not in opts
    assert opts["sfUrl"] == "acc.snowflakecomputing.com"


# ---------- writers ----------

def test_write_files_with_partitions():
    df = fake_df()
    write_files(df, "s3://b/out/", fmt="parquet", mode="append", partition_by=["load_date"])
    assert df.write.args("mode") == [("append",)]
    assert df.write.args("partitionBy") == [("load_date",)]
    assert df.write.args("save") == [("s3://b/out/",)]


def test_write_snowflake_pre_and_post_actions():
    df = fake_df()
    write_snowflake(df, SF, table="STG_ORDERS", mode="overwrite", preactions="TRUNCATE TABLE STG_ORDERS")
    opts = df.write.recorded_options()
    assert opts["dbtable"] == "STG_ORDERS" and opts["preactions"] == "TRUNCATE TABLE STG_ORDERS"
    assert "postactions" not in opts
    assert df.write.args("mode") == [("overwrite",)]
    assert df.write.args("save") == [()]


def test_write_jdbc():
    df = fake_df()
    write_jdbc(df, JDBC, table="public.target")
    opts = df.write.recorded_options()
    assert opts["dbtable"] == "public.target" and opts["driver"] == JDBC.driver
    assert df.write.args("mode") == [("append",)]


def test_write_delta_without_merge_keys_saves_table():
    df = fake_df()
    df.sparkSession = None
    write_delta(df, "c.s.t", mode="overwrite")
    assert df.write.args("mode") == [("overwrite",)]
    assert df.write.args("saveAsTable") == [("c.s.t",)]
