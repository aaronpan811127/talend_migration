"""Shared pytest fixtures. `src/` and `tests/` are on sys.path via pytest.ini."""
import sys

import pytest

sys.dont_write_bytecode = True  # keep __pycache__ out of the workspace / repo


@pytest.fixture(scope="session")
def spark():
    """Spark session: the Databricks runtime session, else Databricks Connect, else local pyspark."""
    try:
        from databricks.sdk.runtime import spark as runtime_spark

        if runtime_spark is not None:
            return runtime_spark
    except Exception:
        pass
    try:
        from databricks.connect import DatabricksSession

        return DatabricksSession.builder.getOrCreate()
    except Exception:
        pass
    try:
        from pyspark.sql import SparkSession

        return SparkSession.builder.master("local[1]").appName("talend_migration_tests").getOrCreate()
    except Exception as exc:  # pragma: no cover
        pytest.skip(f"no Spark session available: {exc}")
