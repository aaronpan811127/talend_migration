"""Reusable source readers (replace Talend tFileInput*, tDBInput, tSnowflakeInput)."""
from typing import Optional

from pyspark.sql import DataFrame, SparkSession

from .config import JdbcConfig, SnowflakeConfig


def read_files(
    spark: SparkSession,
    path: str,
    fmt: str = "csv",
    options: Optional[dict] = None,
    schema: Optional[str] = None,
) -> DataFrame:
    """Read files from S3 / UC Volumes (csv, json, parquet, avro, text, xml, ...)."""
    defaults = {"header": "true"} if fmt == "csv" else {}
    reader = spark.read.format(fmt).options(**{**defaults, **(options or {})})
    if schema:
        reader = reader.schema(schema)
    return reader.load(path)


def read_table(spark: SparkSession, table: str) -> DataFrame:
    """Read a Unity Catalog table (catalog.schema.table)."""
    return spark.read.table(table)


def read_jdbc(
    spark: SparkSession,
    cfg: JdbcConfig,
    table: Optional[str] = None,
    query: Optional[str] = None,
    options: Optional[dict] = None,
) -> DataFrame:
    """Read an RDBMS source over JDBC. Pass exactly one of table or query."""
    if bool(table) == bool(query):
        raise ValueError("Provide exactly one of table or query")
    reader = (
        spark.read.format("jdbc")
        .option("url", cfg.url)
        .option("user", cfg.user)
        .option("password", cfg.password)
    )
    if cfg.driver:
        reader = reader.option("driver", cfg.driver)
    reader = reader.option("dbtable", table) if table else reader.option("query", query)
    return reader.options(**(options or {})).load()


def read_snowflake(
    spark: SparkSession,
    cfg: SnowflakeConfig,
    table: Optional[str] = None,
    query: Optional[str] = None,
) -> DataFrame:
    """Read a Snowflake table or query with the built-in Spark Snowflake connector."""
    if bool(table) == bool(query):
        raise ValueError("Provide exactly one of table or query")
    reader = spark.read.format("snowflake").options(**cfg.spark_options())
    reader = reader.option("dbtable", table) if table else reader.option("query", query)
    return reader.load()
