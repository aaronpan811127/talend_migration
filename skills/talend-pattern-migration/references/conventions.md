# Conventions for parallel migration work

## Ownership (avoids merge conflicts)

Each pattern has exactly one owner (see `migration/pattern_NN/jobs.csv`). The owner, and their agent, only touch:

| Path | Owner |
| --- | --- |
| `notebooks/pattern_NN/**` | pattern owner |
| `resources/jobs/pattern_NN_*.job.yml` | pattern owner |
| `migration/pattern_NN/**` | pattern owner |
| `tests/patterns/pattern_NN/**` | pattern owner |
| `src/operators/**`, `tests/unit/**`, `tests/static/**`, `tests/conftest.py`, `tests/project.py`, `pytest.ini`, `databricks.yml`, `skills/**`, `notebooks/validate_pattern`, `AGENTS.md`, `CLAUDE.md` | shared - platform owner reviews |

Shared changes go in their own small branch/PR (`shared/<topic>`), separate from pattern work, and need a unit-style test or a dev run. Adding a new function is fine; changing an existing signature needs every pattern owner's sign-off.

## Git and environments

* Each person works in their own Git folder clone of the repo, on branch `migrate/pattern_NN`.
* Deploy only with `--target dev`. Each deploy goes into a **lane** (bundle variable `lane`): its own folder `~/.bundle/talend_migration/dev/<lane>` (so its own state and deployment lock), job-name prefix `[dev <user> <lane>]` and Snowflake schema. People use the default lane `main`. Anything that deploys in parallel under the same identity - Omnigent sub-agents, several terminals, CI jobs - passes `--var lane=pattern_NN` (or sets `BUNDLE_VAR_lane`), one lane per pattern.
* Lanes isolate deploys, jobs and Snowflake data, not source code: each parallel agent still needs its own Git clone or worktree.
* Prod deploys happen from `main` through CI or the platform owner, never from a pattern branch.

## Naming

* Pattern id: `pattern_NN` (two digits, `pattern_01`..`pattern_13`).
* Notebooks: one folder per family, `notebooks/pattern_NN/`, holding one or more notebooks named `NN_<step>` in run order (e.g. `01_extract_load`, `02_transform`). Each notebook is one job task.
* Helper modules: plain `.py` files in the same folder (e.g. `transforms.py`) for logic you want to unit test.
* Job file / key: `resources/jobs/pattern_NN_<talend_job_snake>.job.yml`, key `pattern_NN_<talend_job_snake>`, `name` same as key.
* Tags on every job: `source: talend`, `pattern: pattern_NN`, `talend_job: <original Talend job name>`.

## Parameters

Common job parameters (every job, same names):

| Name | Value |
| --- | --- |
| `job_name` | job key |
| `src_path` | `${workspace.file_path}/src` |
| `catalog`, `schema` | `${var.catalog}`, `${var.schema}` |
| `snowflake_secret_scope` | `${var.snowflake_secret_scope}` |
| `snowflake_schema` | `${var.snowflake_schema}` |

Pattern-specific parameters: snake_case versions of the Talend context variable names. Job parameters are passed to every task. Every notebook declares the common widgets plus the pattern parameters it uses; every job parameter must be read by at least one of the job's notebooks.

## Snowflake in dev

* Each developer and lane has its own shadow schema, `MIGRATION_DEV_<short_name>_<lane>` (bundle variable `snowflake_schema`, from `${workspace.current_user.short_name}` and `${var.lane}`; `aaron.pan@...` gets `MIGRATION_DEV_aaron_pan_main`, and with `--var lane=pattern_01` `MIGRATION_DEV_aaron_pan_pattern_01`). Parallel dev runs never overwrite each other's tables.
* Snowflake table **and procedure** parameters are **unqualified** (`STG_ORDERS`, `SP_TRANSFORM_ORDERS`, not `DEV_DB.X.STG_ORDERS` or `ETL.SP_...`). `call_procedure` qualifies an unqualified name as `<database>.<snowflake_schema>.<name>`, so each developer calls the copy in their own schema and Snowflake's search path never picks a shared one. Notebooks build `SnowflakeConfig.from_secrets(..., schema=p["snowflake_schema"])`, so unqualified names resolve in the shadow schema in dev and in the prod schema in prod. Never hard-code `MIGRATION_DEV...` in code or YAML.
* In `validation.yml`, Snowflake `actual` datasets reference `${snowflake_schema}` (e.g. `DEV_DB.${snowflake_schema}.STG_ORDERS`); `validate_pattern` fills it from its `snowflake_schema` widget.
* Each shadow schema must exist before its first dev run: ask the Snowflake admin to create them (one per developer and lane in use), or to grant CREATE SCHEMA on the dev database.
* Stored procedures: each shadow schema needs its own copy of every procedure the pattern calls, and that copy must use unqualified table names or `CURRENT_SCHEMA()` - a body that hard-codes `ETL.` still writes shared tables. Until the Snowflake owner confirms this, keep the component `needs_input` in `components.yml`. In prod, set `snowflake_schema` to the schema the procedures live in.

## Inventory (`migration/pattern_NN/jobs.csv`)

One file per pattern, owned by the pattern owner, with columns `talend_job,job_key,owner,status,notes` (the pattern is the folder). Create the folder with a header-only `jobs.csv` when a pattern is claimed. Rules: `job_key` starts with the folder's pattern id; `talend_job` and `job_key` are unique across all patterns; every job YAML is listed in its own pattern's file. For a project-wide view, read all of them with `inventory_rows()` in `tests/project.py`.

## Status values (`jobs.csv`)

`not_started` -> `analyzing` -> `converting` -> `validating` -> `ready_for_review` -> `done` (or `blocked`, with a note).

## Component status file

`migration/pattern_NN/components.yml` records every Talend component in the family and where it stands. It replaces the component mapping table in `spec.md`. Required once any of the pattern's jobs is `converting` or later.

| Field | Required | Meaning |
| --- | --- | --- |
| `name` | yes | Talend component instance, e.g. `tMap_1` (unique) |
| `type` | yes | Talend component type, e.g. `tMap` |
| `mapping` | yes | `standard` (a row of component-mapping.md), `manual` (hand-written, e.g. tJava), `not_needed`, `unsupported` |
| `implementation` | when resolved | operator call or PySpark summary; for `not_needed`, why |
| `notebook`, `cell` | `notebook` when a resolved `standard`/`manual` | notebook stem in `notebooks/pattern_NN/` and exact cell title |
| `status` | yes | `resolved`, `needs_input` (blocked on a human answer), `deferred` (accepted gap, out of scope for now) |
| `reason` | for `needs_input` / `deferred` | the question to answer, or why it is deferred |
| `semantic_deltas` | no | sentences describing behaviour that differs from Talend (types, nulls, ordering, error handling) - reviewers read these |
| `reviewed_by` | `manual` + resolved | email of the human who reviewed the hand-written code |
| `jobs` | no | Talend jobs that use it, if not all of the family |

Rules (`tests/static/test_components.py`): `unsupported` can't be `resolved`; `standard` types must appear in component-mapping.md (otherwise use `manual` or add the row as a shared change); every `[REVIEW]` cell is a `manual` component; no `needs_input` once a job is `ready_for_review` or `done`. `needs_input` and `deferred` items show as warnings on every test run.

## Tests

* `pytest tests/static` checks code and configs for every pattern (no Spark). Run it on Databricks with the `tests/run_tests` notebook (`scope` = `tests/static`) or locally/CI with `pip install -r requirements-dev.txt`.
* Put pattern-specific unit tests in `tests/patterns/pattern_NN/test_pattern_NN_*.py` (see `tests/README.md`).
* Shared operator changes need unit tests in `tests/unit/operators/`.

## Review checklist

`tests/static` enforces the (must) items automatically; a failing test blocks review. Non-must items show as pytest warnings - fix them or explain them in the PR. Read the files for anything the tests can't judge (logic matches Talend, spec complete).

Each notebook in `notebooks/pattern_NN/`:
* (must) First cell is the markdown overview; cell structure follows `notebook-template.md`.
* (must) Has widgets for all common parameters, and imports from `operators` for all I/O and Snowflake calls - no direct `spark.read`, `.write`, or Snowflake connector use.
* (must) No hard-coded credentials, hosts or passwords - secret scope lookups only.
* (must) No f-string or concatenated SQL passed to `execute`, `call_procedure` or `spark.sql` - use bound parameters.
* No literal `s3://` or `/Volumes/` paths - make them parameters.
* No pandas, `toPandas()` or `.rdd` on large data.
* Ends with `dbutils.notebook.exit` and a run summary (row counts).
* No leftover `TODO`; `[REVIEW]` cells are `manual` entries in `components.yml`.

Each job YAML `resources/jobs/pattern_NN_*.job.yml`:
* (must) Defines exactly one job whose key equals the file stem; `name` equals the key.
* (must) Tags `source: talend`, `pattern: pattern_NN`, `talend_job: <original name>`.
* (must) Every `notebook_task` points at an existing notebook inside `notebooks/pattern_NN/`; task keys are unique and `depends_on` has no unknown tasks or cycles.
* (must) Has all common parameters with their standard defaults, and every parameter is read by a widget in one of its notebooks.
* Any `schedule` has `pause_status: PAUSED`.

Pattern folder and inventory:
* (must) `components.yml` follows the component status rules.
* (must) `spec.md` and `validation.yml` exist; `validation.yml` has at least one check, each with `expected.type` and `actual.type`.
* Talend `.item` exports are in `migration/pattern_NN/talend/`.
* (must) Every job file has a row in its pattern's `jobs.csv` with the same `job_key`, and vice versa.
* (must) Snowflake table and procedure parameters are unqualified; notebooks pass `schema=p["snowflake_schema"]`; `validation.yml` Snowflake `actual` datasets use `${snowflake_schema}`.

## Definition of done for a pattern

1. `spec.md` complete, no unresolved Open questions; `components.yml` has no `needs_input`, and every `deferred` item is agreed with the reviewer.
2. `pytest tests/static tests/patterns/pattern_NN` passes; `bundle validate --strict --target dev` passes.
3. Every job in the family ran successfully in dev.
4. `validation.yml` reconciliation PASS for every job on at least one representative load (ideally 2-3 different business dates), recorded in `validation_results.md`.
5. Reviewed and merged to `main`.
