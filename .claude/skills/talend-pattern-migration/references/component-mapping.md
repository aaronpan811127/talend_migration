# Talend to Databricks mapping

Starting guidance for converting by hand - there is no converter script. `MANUAL` means no standard mapping: the pattern owner decides and records it in the spec. When you work out a mapping for your pattern that others can reuse, add it here as a shared change.

## Components

| Talend component(s) | Databricks equivalent |
| --- | --- |
| tFileInputDelimited, tFileInputExcel, tFileInputJSON, tFileInputXML, tFileInputParquet, tFileInputPositional | `read_files(spark, path, fmt=...)` (csv/excel/json/xml/parquet/text) |
| tS3Connection, tS3Get, tS3List | Not needed - read `s3://` paths directly through a Unity Catalog external location with `read_files` |
| tS3Put, tFileOutputDelimited, tFileOutputParquet, tFileOutputJSON | `write_files(df, path, fmt=...)` |
| tS3Delete, tFileDelete, tFileCopy | `dbutils.fs.rm` / `dbutils.fs.cp` |
| tFileList, tFileExist | `dbutils.fs.ls` |
| tDBInput, tMysqlInput, tOracleInput, tMSSqlInput, tPostgresqlInput | `read_jdbc(spark, JdbcConfig.from_secrets(...), query=...)` (or Lakehouse Federation) |
| tDBOutput, tMysqlOutput, tOracleOutput, tMSSqlOutput, tPostgresqlOutput | `write_jdbc(df, cfg, table, mode)` |
| tDBRow, tOracleRow, tMSSqlRow (DML/DDL) | MANUAL - needs a Python DB driver operator (shared change) |
| tSnowflakeConnection, tSnowflakeClose, tSnowflakeCommit, tSnowflakeRollback | `SnowflakeConfig.from_secrets(dbutils, scope)`; open/close handled by `SnowflakeClient` |
| tSnowflakeInput | `read_snowflake(spark, sf_cfg, table=... or query=...)` |
| tSnowflakeOutput, tSnowflakeOutputBulk, tSnowflakeOutputBulkExec, tSnowflakeBulkExec | `write_snowflake(df, sf_cfg, table, mode, preactions, postactions)` |
| tSnowflakeRow (SQL) | `SnowflakeClient(sf_cfg).execute(sql, params)` - bind values, never f-string them |
| tSnowflakeRow with `CALL`, tSnowflakeSP | `call_procedure(sf_cfg, p["snowflake_procedure"], [args])` with an **unqualified** name - called as `<database>.<snowflake_schema>.PROC` (needs a copy in each shadow schema; see conventions) |
| tMap | `select` / `withColumn` / `join` (lookup = left join; inner-join reject = `left_anti`); multiple outputs = multiple DataFrames from the same input |
| tFilterRow | `filter` (rejects = `filter(~cond)`) |
| tAggregateRow | `groupBy(...).agg(...)` |
| tSortRow | `orderBy` (only if order matters for the target) |
| tUniqRow | `dropDuplicates(keys)`; duplicates output = window `row_number() > 1` |
| tJoin | `join` |
| tUnite | `unionByName(allowMissingColumns=True)` |
| tReplicate | reuse the DataFrame |
| tNormalize / tDenormalize | `explode(split(...))` / `groupBy().agg(concat_ws(sep, collect_list(...)))` |
| tConvertType | `cast` |
| tReplace | `regexp_replace` |
| tSchemaComplianceCheck | `filter` with explicit rules; rejects to a quarantine table |
| tFixedFlowInput, tRowGenerator | `spark.createDataFrame` |
| tSetGlobalVar, globalMap | Python variables; across tasks `dbutils.jobs.taskValues` |
| tContextLoad, context variables | Job parameters + widgets; secrets in secret scope |
| tRunJob | Extra task with `depends_on` (same pattern) or `run_job_task` (other pattern) |
| tPrejob / tPostjob | First / last cells, or separate setup/teardown tasks |
| tLoop, tFlowToIterate, tForeach | Python loop, or `for_each_task` for parallel iterations |
| tParallelize | Parallel tasks in the job |
| tSleep | `time.sleep` (or job retry settings) |
| tWarn | `print` / logging |
| tDie | `raise Exception(message)` |
| tLogCatcher, tStatCatcher, tFlowMeter, tLogRow | Job run history, `email_notifications`, `dbutils.notebook.exit(summary)` |
| tSendMail | `email_notifications` / `webhook_notifications` on the job |
| tFTP*, tSFTP* | MANUAL - Lakeflow Connect SFTP or a new reader operator |
| tREST, tRESTClient, tHttpRequest | MANUAL - new reader operator using `requests` |
| tJava, tJavaRow, tJavaFlex, custom routines | MANUAL - rewrite in PySpark, mark cell `[REVIEW]` |

## Common Java expressions in tMap

| Talend / Java | PySpark (`F` = `pyspark.sql.functions`) |
| --- | --- |
| `row1.col == null ? x : row1.col` | `F.coalesce(F.col("col"), F.lit(x))` |
| `Relational.ISNULL(row1.col)` | `F.col("col").isNull()` |
| `cond ? a : b` | `F.when(cond, a).otherwise(b)` |
| `StringHandling.UPCASE(s)` / `s.toUpperCase()` | `F.upper(s)` |
| `StringHandling.TRIM(s)` / `s.trim()` | `F.trim(s)` |
| `s.substring(a, b)` | `F.substring(s, a + 1, b - a)` (1-based) |
| `s1 + s2` (strings) | `F.concat(s1, s2)` (null if any null) or `F.concat_ws("", ...)` |
| `s.equals("X")` | `F.col("s") == "X"` |
| `TalendDate.getCurrentDate()` | `F.current_timestamp()` |
| `TalendDate.parseDate("yyyy-MM-dd", s)` | `F.to_date(s, "yyyy-MM-dd")` / `F.to_timestamp` |
| `TalendDate.formatDate("yyyyMMdd", d)` | `F.date_format(d, "yyyyMMdd")` |
| `TalendDate.addDate(d, n, "dd")` | `F.date_add(d, n)` |
| `Numeric.sequence("s", 1, 1)` | `F.row_number().over(window)` or `F.monotonically_increasing_id()` |
| `Integer.parseInt(s)` / `Double.parseDouble(s)` | `F.col(s).cast("int")` / `.cast("double")` |
| `BigDecimal` arithmetic | `cast("decimal(p,s)")` - keep Snowflake precision |

Watch for: Java date patterns are compatible with Spark for common cases but `u`, `Y` and `S` differ; Talend's empty string vs null handling (set `nullValue`/`emptyValue` in CSV options to match); trailing delimiter and header/footer row settings of tFileInputDelimited (`HEADER`, `FOOTER`, `FIELDSEPARATOR`, `ENCODING`, `TEXT_ENCLOSURE`).
