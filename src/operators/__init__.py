"""Reusable operators for Talend-migrated jobs.

Named `operators` (not `operator`) to avoid shadowing Python's built-in `operator` module.
"""
from .config import JdbcConfig, SnowflakeConfig
from .readers import read_files, read_jdbc, read_snowflake, read_table
from .snowflake import SnowflakeClient, call_procedure
from .validation import compare_dataframes, run_from_config
from .writers import write_delta, write_files, write_jdbc, write_snowflake

__all__ = [
    "JdbcConfig",
    "SnowflakeConfig",
    "SnowflakeClient",
    "call_procedure",
    "compare_dataframes",
    "run_from_config",
    "read_files",
    "read_jdbc",
    "read_snowflake",
    "read_table",
    "write_delta",
    "write_files",
    "write_jdbc",
    "write_snowflake",
]
