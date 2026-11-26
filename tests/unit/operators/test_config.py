"""Unit tests for operators.config (no Spark needed)."""
import dataclasses

import pytest

from operators.config import JdbcConfig, SnowflakeConfig

SF_SECRETS = {
    "account": "xy12345.us-east-1",
    "user": "etl_user",
    "password": "pw",
    "role": "ETL_ROLE",
    "warehouse": "ETL_WH",
    "database": "DEV_DB",
}


class FakeSecrets:
    def __init__(self, values):
        self.values = values
        self.calls = []

    def get(self, scope, key):
        self.calls.append((scope, key))
        if key not in self.values:
            raise KeyError(key)  # dbutils.secrets.get raises for a missing key
        return self.values[key]


class FakeDbutils:
    def __init__(self, values):
        self.secrets = FakeSecrets(values)


def test_snowflake_from_secrets_reads_every_key_from_the_scope():
    dbutils = FakeDbutils(SF_SECRETS)
    cfg = SnowflakeConfig.from_secrets(dbutils, scope="snowflake-dev")
    assert cfg.account == "xy12345.us-east-1"
    assert cfg.database == "DEV_DB"
    assert cfg.schema == "PUBLIC"
    assert {s for s, _ in dbutils.secrets.calls} == {"snowflake-dev"}
    assert {k for _, k in dbutils.secrets.calls} == set(SF_SECRETS)


def test_snowflake_schema_override():
    cfg = SnowflakeConfig.from_secrets(FakeDbutils(SF_SECRETS), scope="s", schema="MIGRATION_DEV")
    assert cfg.schema == "MIGRATION_DEV"


def test_snowflake_missing_secret_raises():
    values = {k: v for k, v in SF_SECRETS.items() if k != "password"}
    with pytest.raises(KeyError):
        SnowflakeConfig.from_secrets(FakeDbutils(values), scope="s")


def test_snowflake_spark_options():
    opts = SnowflakeConfig(**SF_SECRETS).spark_options()
    assert opts["sfUrl"] == "xy12345.us-east-1.snowflakecomputing.com"
    assert opts["sfUser"] == "etl_user"
    assert opts["sfDatabase"] == "DEV_DB"
    assert opts["sfSchema"] == "PUBLIC"


def test_snowflake_connector_kwargs():
    kw = SnowflakeConfig(**SF_SECRETS, schema="X").connector_kwargs()
    assert kw == {**SF_SECRETS, "schema": "X"}


def test_configs_are_immutable():
    cfg = SnowflakeConfig(**SF_SECRETS)
    with pytest.raises(dataclasses.FrozenInstanceError):
        cfg.password = "changed"


def test_jdbc_driver_is_optional():
    cfg = JdbcConfig.from_secrets(FakeDbutils({"url": "jdbc:x", "user": "u", "password": "p"}), scope="s")
    assert cfg == JdbcConfig(url="jdbc:x", user="u", password="p", driver=None)


def test_jdbc_prefix_and_driver():
    secrets = {"ora_url": "jdbc:oracle", "ora_user": "u", "ora_password": "p", "ora_driver": "oracle.jdbc.OracleDriver"}
    cfg = JdbcConfig.from_secrets(FakeDbutils(secrets), scope="s", prefix="ora_")
    assert cfg.url == "jdbc:oracle"
    assert cfg.driver == "oracle.jdbc.OracleDriver"
