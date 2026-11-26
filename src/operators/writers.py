"""Reusable target writers (replace Talend tFileOutput*, tS3Put, tSnowflakeOutput, tDBOutput)."""
from typing import List, Optional

from pyspark.sql import DataFrame

from .config import JdbcConfig, SnowflakeConfig


def write_files(
    df: DataFrame,
    path: str,
    fmt: str = "parquet",
    mode: str = "overwrite",
    partition_by: Optional[List[str]] = None,
    options: Optional[dict] = None,
) -> None:
    """Write files to S3 / UC Volumes (e.g. the landing zone)."""
    writer = df.write.format(fmt).mode(mode).options(**(options or {}))
    if partition_by:
        writer = writer.partitionBy(*partition_by)
    writer.save(path)


def write_delta(
    df: DataFrame,
    table: str,
    mode: str = "append",
    merge_keys: Optional[List[str]] = None,
) -> None:
    """Write to a Unity Catalog Delta table. If merge_keys is set, upsert with MERGE."""
    spark = df.sparkSession
    if not merge_keys:
        df.write.mode(mode).saveAsTable(table)
        return
    if not spark.catalog.tableExists(table):
        df.write.saveAsTable(table)
        return
    from delta.tables import DeltaTable

    cond = " AND ".join(f"t.`{k}` = s.`{k}`" for k in merge_keys)
    (
        DeltaTable.forName(spark, table).alias("t")
        .merge(df.alias("s"), cond)
        .whenMatchedUpdateAll()
        .whenNotMatchedInsertAll()
        .execute()
    )


def write_snowflake(
    df: DataFrame,
    cfg: SnowflakeConfig,
    table: str,
    mode: str = "append",
    preactions: Optional[str] = None,
    postactions: Optional[str] = None,
) -> None:
    """Bulk-load a DataFrame into Snowflake with the built-in Spark Snowflake connector."""
    writer = df.write.format("snowflake").options(**cfg.spark_options()).option("dbtable", table)
    if preactions:
        writer = writer.option("preactions", preactions)
    if postactions:
        writer = writer.option("postactions", postactions)
    writer.mode(mode).save()


def write_jdbc(
    df: DataFrame,
    cfg: JdbcConfig,
    table: str,
    mode: str = "append",
    options: Optional[dict] = None,
) -> None:
    """Write to an RDBMS target over JDBC."""
    writer = (
        df.write.format("jdbc")
        .option("url", cfg.url)
        .option("user", cfg.user)
        .option("password", cfg.password)
        .option("dbtable", table)
    )
    if cfg.driver:
        writer = writer.option("driver", cfg.driver)
    writer.options(**(options or {})).mode(mode).save()
