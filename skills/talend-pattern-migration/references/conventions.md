# Conventions for parallel migration work

## Ownership (avoids merge conflicts)

Each pattern has exactly one owner (see `migration/pattern_NN/jobs.csv`). The owner, and their agent, only touch:

| Path | Owner |
| --- | --- |
| `notebooks/pattern_NN/**` | pattern owner |
| `resources/jobs/pattern_NN_*.job.yml` | pattern owner |
| `migration/pattern_NN/**` | pattern owner |
| `tests/patterns/pattern_NN/**` | pattern owner |
| `src/operators/**`, `tests/unit/**`, `tests/static/**`, `tests/conftest.py`, `tests/project.py`, `pytest.ini`, `databricks.yml`, `skills/**`, `notebooks/validate_pattern`, `AGENTS.md`, `CLAUDE.md`, `.gitignore`, `.github/**` | shared - platform owner reviews |

Shared changes go in their own small `shared/<topic>/...` branch and PR, separate from pattern work (the pattern PR is stacked on it, see below), and need a unit-style test or a dev run. Adding a new function is fine; changing an existing signature needs every pattern owner's sign-off.

## Git and environments

The repo is `https://github.com/aaronpan811127/talend_migration` (default branch `main`). The Git folder `/Workspace/Users/aaron.pan@databricks.com/talend_migration` is the reference checkout: read it, don't do pattern work in it.

### Branches

Every session (an Omnigent sandbox session, or a person's Genie Code session) creates its own branches. The same pattern gets new branches over time; branches are never reused across sessions.

| Branch | Name | Changes | Based on |
| --- | --- | --- | --- |
| Migration | `migrate/pattern_NN/<YYYYMMDD-HHMM>-<session>` | only that pattern's files | the session's shared branch if it has one, else `origin/main` |
| Shared | `shared/<topic>/<YYYYMMDD-HHMM>-<session>` | shared files (`src/operators`, `databricks.yml`, `skills/`, ...) | `origin/main` |

* `<YYYYMMDD-HHMM>` is the session's start time in **UTC** (`date -u +%Y%m%d-%H%M`); `<session>` is the session name, lowercased with anything other than `a-z0-9` replaced by `-`, at most 40 characters. `<topic>` is a short lowercase slug, e.g. `read-files-incremental`. Example: `migrate/pattern_01/20261126-1015-orders-load` stacked on `shared/read-files-incremental/20261126-1015-orders-load`.
* Never create a plain `migrate/pattern_NN` or `shared/<topic>` branch: git can't hold both `x` and `x/...`, so one would block the whole pattern or topic.
* Never commit to `main`. Everything reaches `main` through reviewed PRs.
* `tests/static/test_git_ownership.py` checks the name format and fails if a migration branch changes anything outside its pattern's files, compared with the shared branch it is stacked on (or `origin/main`).
* **One active session per pattern at a time**, because a pattern's dev lane (`--var lane=pattern_NN`) and Snowflake schema are per pattern, not per session. A new session for the same pattern starts after the previous session's PRs are merged or closed.

### Working copy

Each session has its own clone of the repo and nobody else uses it - in an Omnigent sandbox, e.g. `git clone https://github.com/aaronpan811127/talend_migration ~/talend_migration`; for a person in Genie Code, their own Git folder (Workspace > Create > Git folder). No `git worktree`. Each clone checks out only its own session's branches.

### Stacked PRs

A pattern is delivered as one migration PR, stacked on a shared PR when it needs shared changes. The agent creates the PRs; a human reviews and merges them, bottom first.

1. **Shared change needed?** Create the shared branch from `origin/main`, commit only shared files (`shared: <what>`), push, open PR **shared -> `main`** titled `shared: <topic>`.
2. **Migration branch.** Create it from the shared branch (or from `origin/main` if there is no shared change), commit only the pattern's files (`pattern_NN: <what>`), push, open PR **migrate -> shared branch** (or -> `main`) titled `pattern_NN: <summary>`, with "Stacked on #<shared PR>" at the top of the description.
3. **Shared change discovered later.** Create the shared branch from `origin/main` and open its PR, then `git merge` it into the migration branch and point the migration PR at it (`gh pr edit <n> --base <shared branch>`). Merge, never rebase pushed branches.
4. **Review fixes.** Push more commits to the same branch. After changing the shared branch, merge it into the migration branch again.
5. **After the shared PR merges,** point the migration PR at `main` if GitHub hasn't already (`gh pr edit <n> --base main`), merge `origin/main` into the migration branch, rerun the tests and push.
6. **PR description** (`.github/pull_request_template.md`): stack position, open `needs_input` / `deferred` components, test output, dev run URLs, reconciliation results.

Rules: commit small; run `pytest tests/static tests/patterns/pattern_NN` before every push; push only your own session's branches; no force-push, no rebasing pushed commits, no deleting other sessions' branches; agents create PRs but never approve or merge them. Creating PRs from a sandbox needs the `gh` CLI (or the GitHub API) with GitHub credentials provided by the session - never stored in the repo.

### Deploying

* Deploy only with `--target dev`. Each deploy goes into a **lane** (bundle variable `lane`): its own folder `~/.bundle/talend_migration/dev/<lane>` (so its own state and deployment lock), job-name prefix `[dev <user> <lane>]` and Snowflake schema. People use the default lane `main`. Anything that deploys in parallel under the same identity - Omnigent sub-agents, several terminals, CI jobs - passes `--var lane=pattern_NN` (or sets `BUNDLE_VAR_lane`), one lane per pattern.
* Lanes isolate deploys, jobs and Snowflake data; the session's own clone isolates source. A deploy from a sandbox clone uploads that clone's files to the lane's folder; a deploy from a workspace Git folder runs that folder's files in place. Either way, jobs run exactly what's in your working copy, committed or not.
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
5. The session's PRs (migration PR, stacked on its shared PR if any) are reviewed and merged to `main` by a human.
