"""Data reconciliation between Talend output (expected) and Databricks output (actual).

Used by the talend-migration-validation skill and notebooks/validate_pattern.
Config format: see migration/<pattern>/validation.yml.
"""
import json
import re
from typing import Any, Dict, List, Optional

from pyspark.sql import DataFrame, SparkSession
from pyspark.sql import functions as F
from pyspark.sql.types import NumericType

from .config import SnowflakeConfig
from .readers import read_files, read_snowflake, read_table


def _normalize(df: DataFrame, ignore_columns: Optional[List[str]]) -> DataFrame:
    """Lower-case column names (Snowflake is upper-case, Delta is usually lower) and drop ignored columns."""
    df = df.toDF(*[c.lower() for c in df.columns])
    ignore = {c.lower() for c in (ignore_columns or [])}
    return df.drop(*[c for c in df.columns if c in ignore])


def compare_dataframes(
    expected: DataFrame,
    actual: DataFrame,
    keys: Optional[List[str]] = None,
    ignore_columns: Optional[List[str]] = None,
    numeric_tolerance: float = 0.0,
    sample_size: int = 10,
) -> Dict:
    """Compare two DataFrames and return a JSON-serialisable report with a `passed` flag.

    Checks: schema (missing / extra / type differences), row counts, and either a keyed
    column-by-column diff (when keys are given) or a full-row multiset diff (exceptAll).
    """
    e = _normalize(expected, ignore_columns)
    a = _normalize(actual, ignore_columns)
    keys = [k.lower() for k in (keys or [])]

    e_types = dict(e.dtypes)
    a_types = dict(a.dtypes)
    common = [c for c in e.columns if c in a_types]
    report: Dict = {
        "missing_columns": sorted(set(e_types) - set(a_types)),
        "extra_columns": sorted(set(a_types) - set(e_types)),
        "type_differences": {c: [e_types[c], a_types[c]] for c in common if e_types[c] != a_types[c]},
        "expected_rows": e.count(),
        "actual_rows": a.count(),
    }

    missing_keys = [k for k in keys if k not in common]
    if missing_keys:
        report["error"] = f"Key columns not in both datasets: {missing_keys}"
        report["passed"] = False
        return report

    if keys:
        report["expected_duplicate_keys"] = e.groupBy(*keys).count().filter("count > 1").count()
        report["actual_duplicate_keys"] = a.groupBy(*keys).count().filter("count > 1").count()

        value_cols = [c for c in common if c not in keys]
        es = e.select(*keys, *[F.col(c).alias(f"e__{c}") for c in value_cols]).withColumn("_in_e", F.lit(1))
        as_ = a.select(*keys, *[F.col(c).alias(f"a__{c}") for c in value_cols]).withColumn("_in_a", F.lit(1))
        j = es.join(as_, on=keys, how="full_outer")

        numeric = {f.name for f in e.schema.fields if isinstance(f.dataType, NumericType)}
        diff_conds = {}
        for c in value_cols:
            ec, ac = F.col(f"e__{c}"), F.col(f"a__{c}")
            if c in numeric and numeric_tolerance > 0:
                cond = (ec.isNull() != ac.isNull()) | (F.abs(ec.cast("double") - ac.cast("double")) > numeric_tolerance)
            elif e_types[c] != a_types[c]:
                cond = ~ec.cast("string").eqNullSafe(ac.cast("string"))
            else:
                cond = ~ec.eqNullSafe(ac)
            diff_conds[c] = cond

        both = F.col("_in_e").isNotNull() & F.col("_in_a").isNotNull()
        aggs = [
            F.sum(F.when(F.col("_in_a").isNull(), 1).otherwise(0)).alias("missing_in_actual"),
            F.sum(F.when(F.col("_in_e").isNull(), 1).otherwise(0)).alias("extra_in_actual"),
        ] + [F.sum(F.when(both & cond, 1).otherwise(0)).alias(f"diff__{c}") for c, cond in diff_conds.items()]
        stats = j.agg(*aggs).first().asDict()

        report["missing_in_actual"] = int(stats.pop("missing_in_actual") or 0)
        report["extra_in_actual"] = int(stats.pop("extra_in_actual") or 0)
        col_diffs = {k[len("diff__"):]: int(v or 0) for k, v in stats.items() if v}
        report["column_mismatches"] = col_diffs

        if col_diffs and sample_size:
            any_diff = F.lit(False)
            for c in col_diffs:
                any_diff = any_diff | diff_conds[c]
            sample_cols = keys + [x for c in col_diffs for x in (f"e__{c}", f"a__{c}")]
            report["mismatch_sample"] = [
                {k: str(v) for k, v in r.asDict().items()}
                for r in j.filter(both & any_diff).select(*sample_cols).limit(sample_size).collect()
            ]
        passed = (
            report["missing_in_actual"] == 0
            and report["extra_in_actual"] == 0
            and not col_diffs
            and report["actual_duplicate_keys"] == report["expected_duplicate_keys"]
        )
    else:
        # No keys: full-row multiset comparison on common columns, compared as strings.
        es = e.select(*[F.col(c).cast("string").alias(c) for c in common])
        as_ = a.select(*[F.col(c).cast("string").alias(c) for c in common])
        report["rows_only_in_expected"] = es.exceptAll(as_).count()
        report["rows_only_in_actual"] = as_.exceptAll(es).count()
        passed = report["rows_only_in_expected"] == 0 and report["rows_only_in_actual"] == 0

    report["passed"] = bool(
        passed and not report["missing_columns"] and report["expected_rows"] == report["actual_rows"]
    )
    return report


def load_dataset(spark: SparkSession, spec: Dict, sf_cfg: Optional[SnowflakeConfig] = None) -> DataFrame:
    """Load a dataset described by a validation.yml `expected` / `actual` block."""
    kind = spec["type"]
    if kind == "snowflake":
        if sf_cfg is None:
            raise ValueError("snowflake dataset requires snowflake_secret_scope in the config")
        df = read_snowflake(spark, sf_cfg, table=spec.get("table"), query=spec.get("query"))
    elif kind == "table":
        df = read_table(spark, spec["table"])
    elif kind == "files":
        df = read_files(spark, spec["path"], fmt=spec.get("format", "parquet"), options=spec.get("options"))
    else:
        raise ValueError(f"Unknown dataset type: {kind}")
    if spec.get("filter"):
        df = df.filter(spec["filter"])
    return df


_VAR_RX = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}")


def substitute_variables(obj: Any, variables: Optional[Dict[str, str]]) -> Any:
    """Replace ${name} in every string of a parsed validation.yml (e.g. ${snowflake_schema}).

    Raises ValueError for any ${name} without a value, so a check never runs against a wrong table.
    """
    variables = variables or {}
    if isinstance(obj, dict):
        return {k: substitute_variables(v, variables) for k, v in obj.items()}
    if isinstance(obj, list):
        return [substitute_variables(v, variables) for v in obj]
    if isinstance(obj, str):
        missing = sorted({m for m in _VAR_RX.findall(obj) if not variables.get(m)})
        if missing:
            raise ValueError(f"No value for {missing} in '{obj}' - pass variables={{...}}")
        return _VAR_RX.sub(lambda m: str(variables[m.group(1)]), obj)
    return obj


def run_from_config(
    spark: SparkSession,
    dbutils,
    config_path: str,
    check_names: Optional[List[str]] = None,
    variables: Optional[Dict[str, str]] = None,
) -> Dict:
    """Run every check in a validation.yml and return {"passed": bool, "checks": {name: report}}.

    `variables` fills ${name} placeholders, e.g. {"snowflake_schema": "MIGRATION_DEV_jane_doe"}.
    """
    import yaml

    with open(config_path) as fh:
        cfg = substitute_variables(yaml.safe_load(fh), variables)

    sf_cfg = None
    if cfg.get("snowflake_secret_scope"):
        sf_cfg = SnowflakeConfig.from_secrets(dbutils, scope=cfg["snowflake_secret_scope"])

    results = {}
    for check in cfg.get("checks", []):
        if check_names and check["name"] not in check_names:
            continue
        try:
            expected = load_dataset(spark, check["expected"], sf_cfg)
            actual = load_dataset(spark, check["actual"], sf_cfg)
            results[check["name"]] = compare_dataframes(
                expected,
                actual,
                keys=check.get("keys"),
                ignore_columns=check.get("ignore_columns"),
                numeric_tolerance=float(check.get("numeric_tolerance", 0.0)),
            )
        except Exception as exc:  # report and continue with the other checks
            results[check["name"]] = {"passed": False, "error": f"{type(exc).__name__}: {exc}"}

    summary = {"pattern": cfg.get("pattern"), "passed": bool(results) and all(r["passed"] for r in results.values()), "checks": results}
    print(json.dumps(summary, indent=2, default=str))
    return summary
