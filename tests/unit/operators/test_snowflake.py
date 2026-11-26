"""Unit tests for operators.snowflake with a fake snowflake.connector (no Snowflake, no Spark)."""
import sys
import types

import pytest

from operators import snowflake as sf
from operators.config import SnowflakeConfig

CFG = SnowflakeConfig(account="acc", user="u", password="p", role="r", warehouse="wh", database="db")


class FakeCursor:
    def __init__(self, conn):
        self.conn = conn

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def execute(self, sql, params=None):
        self.conn.executed.append((sql, params))

    def fetchall(self):
        if self.conn.fetch_error:
            raise RuntimeError("no result set")
        return self.conn.rows


class FakeConnection:
    def __init__(self):
        self.executed = []
        self.rows = [("OK",)]
        self.fetch_error = False
        self.closed = False
        self.connect_kwargs = None

    def cursor(self):
        return FakeCursor(self)

    def close(self):
        self.closed = True


@pytest.fixture
def conn(monkeypatch):
    c = FakeConnection()

    def connect(**kwargs):
        c.connect_kwargs = kwargs
        return c

    connector = types.ModuleType("snowflake.connector")
    connector.connect = connect
    package = types.ModuleType("snowflake")
    package.connector = connector
    monkeypatch.setitem(sys.modules, "snowflake", package)
    monkeypatch.setitem(sys.modules, "snowflake.connector", connector)
    return c


SHADOW = SnowflakeConfig(account="acc", user="u", password="p", role="r", warehouse="wh", database="DEV_DB",
                         schema="MIGRATION_DEV_jane_doe")


def test_call_procedure_binds_arguments(conn):
    result = sf.call_procedure(CFG, "SP_TRANSFORM_ORDERS", ["job_a", "2026-11-24"])
    assert conn.executed == [("CALL db.PUBLIC.SP_TRANSFORM_ORDERS(%s, %s)", ["job_a", "2026-11-24"])]
    assert result == [("OK",)]


def test_call_procedure_without_arguments(conn):
    sf.call_procedure(CFG, "SP_NOARGS")
    assert conn.executed == [("CALL db.PUBLIC.SP_NOARGS()", [])]


def test_unqualified_procedure_runs_in_shadow_schema(conn):
    """Two developers calling the same unqualified name hit their own schema's copy."""
    sf.call_procedure(SHADOW, "SP_TRANSFORM_ORDERS", ["job_a"])
    other = SnowflakeConfig(**{**SHADOW.__dict__, "schema": "MIGRATION_DEV_john_roe"})
    sf.call_procedure(other, "SP_TRANSFORM_ORDERS", ["job_a"])
    assert [sql for sql, _ in conn.executed] == [
        "CALL DEV_DB.MIGRATION_DEV_jane_doe.SP_TRANSFORM_ORDERS(%s)",
        "CALL DEV_DB.MIGRATION_DEV_john_roe.SP_TRANSFORM_ORDERS(%s)",
    ]


@pytest.mark.parametrize("name,expected", [
    ("SP", "DEV_DB.MIGRATION_DEV_jane_doe.SP"),
    ("ETL.SP", "DEV_DB.ETL.SP"),
    ("OTHER_DB.ETL.SP", "OTHER_DB.ETL.SP"),
    ('"My Proc"', 'DEV_DB.MIGRATION_DEV_jane_doe."My Proc"'),
    ('"My.Db".ETL.SP', '"My.Db".ETL.SP'),
])
def test_qualify_name(name, expected):
    assert sf.qualify_name(name, SHADOW) == expected


@pytest.mark.parametrize("schema", ["", "A.B", "X; DROP", "1BAD"])
def test_invalid_config_schema_is_rejected(conn, schema):
    bad = SnowflakeConfig(**{**SHADOW.__dict__, "schema": schema})
    with pytest.raises(ValueError, match="schema"):
        sf.call_procedure(bad, "SP")
    assert conn.executed == []


def test_connection_uses_config_and_is_closed(conn):
    sf.call_procedure(CFG, "DB.ETL.SP", [1])
    assert conn.connect_kwargs == CFG.connector_kwargs()
    assert conn.closed


def test_connection_closed_on_error(conn):
    with pytest.raises(ValueError):
        with sf.SnowflakeClient(CFG) as client:
            client.call_procedure("bad name;")
    assert conn.closed
    assert conn.executed == []


def test_execute_returns_empty_list_when_no_result_set(conn):
    conn.fetch_error = True
    with sf.SnowflakeClient(CFG) as client:
        assert client.execute("TRUNCATE TABLE X") == []


@pytest.mark.parametrize("name", ["DB.ETL.SP_LOAD$1", '"My Db".ETL."Proc Name"'])
def test_fully_qualified_names_are_kept(conn, name):
    sf.call_procedure(CFG, name)
    assert conn.executed[0][0] == f"CALL {name}()"


@pytest.mark.parametrize(
    "name",
    ["", "SP; DROP TABLE X", "A.B.C.D", "1SP", "SP()", "SP --", "ETL.SP(1)", "ETL..SP", 'ETL."unterminated'],
)
def test_invalid_procedure_names_are_rejected(conn, name):
    with pytest.raises(ValueError):
        sf.call_procedure(CFG, name)
    assert conn.executed == []
