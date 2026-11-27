# pattern_01: S3 to Snowflake with stored procedure

Owner: aaron.pan@databricks.com
Status: converting (reference implementation)

## Talend jobs in this family

* ExampleOrdersLoad (placeholder - replace with the real jobs)

## Flow

1. tFileInputDelimited / tS3Get - read landed files from `source_path`.
2. tSnowflakeOutputBulkExec - load into `snowflake_stage_table` (overwrite).
3. tSnowflakeRow (CALL) - call `snowflake_procedure(job_name)` to transform into the final tables.

## Component mapping

Tracked per component, with status and behaviour differences, in [components.yml](components.yml).

## Parameters

| Parameter | Talend context variable | Same for all jobs? | Example |
| --- | --- | --- | --- |
| source_path | context.s3_path | no | s3://bucket/talend/orders/ |
| source_format | - | usually csv | csv |
| snowflake_stage_table | context.stage_table | no | STG_ORDERS |
| snowflake_procedure | context.sp_name (unqualified) | no | SP_TRANSFORM_ORDERS |

## Snowflake objects

| Object | Type (table / stage / procedure) | Read / write / call | Dev equivalent |
| --- | --- | --- | --- |
| STG_ORDERS | table | write | `STG_ORDERS` in the developer's shadow schema (`MIGRATION_DEV_<short_name>_<lane>`) |
| SP_TRANSFORM_ORDERS (prod: ETL) | procedure | call | Copy in each developer's shadow schema; called as `<db>.MIGRATION_DEV_<short_name>_<lane>.SP_TRANSFORM_ORDERS` |

## Variances between jobs

None known yet.

## Decisions

Choices later sessions and reviewers must not undo without asking. Newest last.

| Date | Decision | Why | Decided by |
| --- | --- | --- | --- |
| 2026-11-24 | Keep Snowflake as the target and keep the Snowflake stored procedure for the transform | Project scope: lift Talend orchestration to Databricks first, no move to Delta yet | aaron.pan@databricks.com |
| 2026-11-25 | Two notebooks, one per task: `01_extract_load`, then `02_transform` | A failed procedure call can be repaired without reloading the stage | aaron.pan@databricks.com |
| 2026-11-26 | Stage table and procedure names are unqualified; the schema comes from `snowflake_schema` | Each developer and lane writes and calls into its own shadow schema | aaron.pan@databricks.com |

## Open questions

* Replace the placeholder job with the real Talend jobs of this family and their exports.
* Component-level questions live in `components.yml` (`status: needs_input`).
* Does the body of `SP_TRANSFORM_ORDERS` hard-code `ETL.` table names? If so, the per-developer copies would still write shared tables; ask the Snowflake owner for a version that uses unqualified names or `CURRENT_SCHEMA()` (tracked in `components.yml`, tSnowflakeRow_1).
