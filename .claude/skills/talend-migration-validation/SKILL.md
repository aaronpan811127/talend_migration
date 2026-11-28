---
name: talend-migration-validation
description: Validate a migrated wave (a set of Talend jobs migrated together) in the talend_migration bundle - review checklist, dev deploy and run, and data reconciliation of Databricks output against Talend output with validation.yml. Read when the user asks to test, validate, reconcile, compare, or sign off a migrated wave or job.
---

# Talend migration validation

Validates one wave (`wave_NN`) converted with the `talend-wave-migration` skill. Read [conventions.md](../talend-wave-migration/references/conventions.md) first - the single source of the rules (ownership, Git, checkpoint, Snowflake in dev, review checklist, definition of done). It belongs to the `talend-wave-migration` skill: with a skill loader (Omnigent `read_skill_file`), read `references/conventions.md` **from that skill**, not via the `../` path, which loaders refuse. This skill adds only the validation steps.

`<root>` = the folder three levels above this skill (`<root>/.claude/skills/talend-migration-validation`).

## Scripts

Reusable validation helpers in `scripts/`, added or changed only on a shared branch (rules: Reusable scripts in conventions.md, read from the `talend-wave-migration` skill). Run from the repo root with `python .claude/skills/talend-migration-validation/scripts/<name>.py --help`.

| Script | What it does | When to use it |
| --- | --- | --- |
| _(none yet)_ | | |

## Step 1 - Review checks (no compute)

* Run `pytest` for `tests/static` and `tests/waves/<wave>` with the `<root>/tests/run_tests` notebook (`scope` widget), or with `executeCode` language `python`: `sys.dont_write_bytecode = True` (`/Workspace` rejects `__pycache__` writes), `os.chdir("<root>")`, then `pytest.main([...])`.
* Read the wave's notebooks, job YAMLs, `spec.md`, `validation.yml` and `jobs.csv` for the checklist items the tests can't judge (`../talend-wave-migration/references/conventions.md`).
* `runDatabricksCli`: `bundle validate --strict --target dev`, `workingDirectory=<root>`.

Stop on any failed test and fix it (or hand back to the conversion skill). Report warnings to the user.

## Step 2 - Deploy and run in dev

* Confirm the dev run writes to the developer's shadow schema: `snowflake_schema` resolves to `MIGRATION_DEV_<short_name>_<lane>` (check with `bundle validate -o json`), table parameters are unqualified, and the schema exists in Snowflake. If a stored procedure writes to fixed production tables, stop and tell the user.
* `bundle deploy --target dev --var lane=<lane>`, then for each job `bundle run <job_key> --target dev --var lane=<lane>` - lanes as in [Deploying](../talend-wave-migration/references/conventions.md#deploying). Override parameters with `--params key=value,...` for a specific business date or input folder.
* If a run fails, load the `job-run-diagnosis` skill. Find the failing task (one per notebook in `notebooks/<wave>/`), fix that notebook, rerun the tests, redeploy, rerun.
* Note the run URL and the row counts from the notebook exit summary.

## Step 3 - Prepare the comparison

Talend and Databricks must process **the same input** (same files / business date / source snapshot). Which Talend runs to compare against is agreed in Phase 1 and recorded in `spec.md` or `validation/validation.yml`. Validation runs in Phase 2 (autonomous): if it isn't recorded, don't wait - add a `needs_input` item with the question, note it in `blocked_on`, and validate what you can.

Edit `<root>/migration/<wave>/validation/validation.yml` - one check per target the jobs write (Snowflake tables, S3 outputs, tables changed by stored procedures):

```yaml
wave: wave_NN
snowflake_secret_scope: snowflake-dev
checks:
  - name: orders_final
    expected: {type: snowflake, table: PROD_DB.ETL.ORDERS_FINAL, filter: "LOAD_DATE = '2026-11-24'"}
    actual:   {type: snowflake, table: "DEV_DB.${snowflake_schema}.ORDERS_FINAL", filter: "LOAD_DATE = '2026-11-24'"}
    keys: [ORDER_ID]            # strongly recommended; without keys a full-row diff is used
    ignore_columns: [LOAD_TS]   # only run-time audit columns - document why
    numeric_tolerance: 0        # > 0 only for float columns, document why
```

Dataset types: `snowflake` (`table` or `query`), `table` (Unity Catalog), `files` (`path`, `format`, `options`). `filter` is a Spark SQL expression applied after loading.

## Step 4 - Run the reconciliation

Either run `notebooks/validate_wave` (widgets `wave` and `snowflake_schema` = the shadow schema the dev run wrote to), or with `executeCode` language `python`:

```python
import sys
sys.path.insert(0, "<root>/src")
from operators.validation import run_from_config
result = run_from_config(spark, dbutils, "<root>/migration/<wave>/validation/validation.yml",
                         variables={"snowflake_schema": "MIGRATION_DEV_<short_name>_<lane>"})
```

The report per check has: `missing_columns`, `extra_columns`, `type_differences`, `expected_rows`, `actual_rows`, and with keys `missing_in_actual`, `extra_in_actual`, duplicate key counts, `column_mismatches` (column -> mismatched rows) and `mismatch_sample`; without keys `rows_only_in_expected` / `rows_only_in_actual`. `passed` is true only when columns, row counts and all values match.

If the compute can't read Snowflake through `format("snowflake")`, run on a classic cluster with the Snowflake connector, or compare through a Lakehouse Federation catalog using `type: table`.

## Step 5 - Triage mismatches

Use `mismatch_sample` to find the cause, then fix the notebook - not the check.

| Symptom | Usual cause |
| --- | --- |
| `type_differences` / decimal mismatches | Talend schema precision vs Spark inference - cast explicitly to the Talend/Snowflake type |
| Strings differ only by whitespace or case | Missing `trim`/`upper` from the tMap, or CSV `ignoreLeadingWhiteSpace` options |
| null vs empty string | CSV `nullValue` / `emptyValue` options, or Talend `== null` vs `.equals("")` logic |
| Timestamps off by hours | Session time zone - set `spark.sql.session.timeZone` to the Talend JVM time zone |
| Row count higher | Missing tFilterRow / tUniqRow, or inner vs left join in tMap |
| Row count lower | Inner join where tMap used left outer, or header/footer rows skipped incorrectly |
| Sequence / surrogate key columns differ | Non-deterministic ordering - order explicitly, or exclude and compare natural keys |
| Stored-procedure output differs but staging matches | Procedure called with different arguments, or ran against different data in dev |

## Step 6 - Record the result

Append to `<root>/migration/<wave>/validation/results.md` (create if missing):

```
## <YYYY-MM-DD> <job_key> - <PASS|FAIL>
* Dev run: <run URL> (<duration, e.g. 14 min>; Talend run took <duration, if known>); Talend run compared: <date / run id>; input: <business date or path>
| Check | Expected rows | Actual rows | Result | Notes |
```

When every job in the wave passes (ideally on 2-3 business dates), set those rows in `migration/<wave>/progress/jobs.csv` to `ready_for_review`.

## Step 7 - Update the PRs

* Commit (in Phase 2 without asking) `validation/results.md`, `jobs.csv` and the checkpoint (`step: pr_review` once the PRs are open) to the migration branch (`<wave>: validation PASS on <dates>`), then hand over and open or update the PRs as in [Resuming and handing over](../talend-wave-migration/references/conventions.md#resuming-and-handing-over) and [PRs](../talend-wave-migration/references/conventions.md#prs). Put the dev run URLs and reconciliation results in the PR body. In Genie Code, give the user compare links instead of `gh`.

## Do not

* Weaken a check to make it pass (new `ignore_columns`, higher tolerance, narrower filter) without telling the user and recording the reason in `validation/results.md`.
* Write to or call procedures on Snowflake production objects. Talend outputs are read-only.
* Deploy to `prod` or unpause schedules.
