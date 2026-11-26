# AGENTS.md

Instructions for coding agents (Claude Code, Codex, Cursor, Omnigent sub-agents, ...) working in this repo. Humans: start with `README.md`.

This is a Declarative Automation Bundle that migrates Talend jobs, grouped into 13 job families (`pattern_01`..`pattern_13`), to Databricks notebooks and jobs. Snowflake stays the target and Snowflake stored procedures stay the transforms. There is no converter: each pattern is converted by hand, following the skills below.

## Your task is one pattern

You work on exactly one `pattern_NN`, named in your prompt. If it isn't, ask. Other agents may be working on other patterns at the same time.

Follow these files in order. They are written for Genie Code but apply to you as-is (tool names are mapped below):

1. `skills/talend-pattern-migration/SKILL.md` - analyze, set up files, spec, convert, job YAMLs, tests.
2. `skills/talend-pattern-migration/references/conventions.md` - ownership, naming, parameters, Snowflake rules, review checklist, definition of done. **Read before changing anything.**
3. `skills/talend-pattern-migration/references/component-mapping.md` and `skills/talend-pattern-migration/references/notebook-template.md`.
4. `skills/talend-migration-validation/SKILL.md` - only when asked to validate.

## Files you may change

Only your pattern's files:

* `notebooks/pattern_NN/`
* `resources/jobs/pattern_NN_*.job.yml`
* `migration/pattern_NN/` (`jobs.csv`, `spec.md`, `components.yml`, `validation.yml`, `validation_results.md`, `talend/`)
* `tests/patterns/pattern_NN/`

Everything else is shared: `src/operators/`, `tests/static/`, `tests/unit/`, `tests/project.py`, `tests/conftest.py`, `pytest.ini`, `databricks.yml`, `skills/`, `notebooks/validate_pattern`, `AGENTS.md`. Don't edit shared files. If you need a shared change (for example a new operator), stop and describe it - signature, behaviour, tests - for a separate `shared/<topic>` PR.

## Tool mapping (Genie Code -> you)

| Skill says | Do this |
| --- | --- |
| `readAssetById` | Read the file. Notebooks are `.ipynb` JSON |
| `editAsset` on a notebook | Edit the `.ipynb` JSON (see Notebooks below) |
| `createAsset` | Create the file |
| `executeCode` language `sh` / `python` | Run it in your shell / Python |
| `runDatabricksCli` `<args>` | `databricks <args>` from the repo root |
| load the `notebook-authoring` skill | Follow the Notebooks section below |
| load the `job-run-diagnosis` skill | `databricks jobs get-run <run_id>` and `databricks jobs get-run-output <task_run_id>`; read the error and the failing cell |
| "ask the user" / "tell the user" | Stop and report back to whoever started you; don't guess |

## Notebooks

* Pattern notebooks are Databricks `.ipynb` files. Keep the notebook-level and cell-level `application/vnd.databricks.v1+...` metadata. Each cell's title is `metadata["application/vnd.databricks.v1+cell"]["title"]`, and the static tests and `components.yml` refer to cells by that title.
* The first cell is markdown: a `# ` heading plus a 1-2 sentence description.
* Python only; I/O and Snowflake calls go through `operators` (`from operators import ...`), never direct `spark.read`, `.write` or `snowflake.connector`.
* Don't run notebooks against Snowflake or S3 from your machine. Correctness is checked by the static tests and by dev runs on Databricks.

## Commands

From the repo root:

```
pip install -r requirements-dev.txt
pytest tests/static tests/patterns/pattern_NN      # must pass; needs no Spark
databricks bundle validate --strict --target dev --var lane=pattern_NN    # must pass
```

If your prompt allows deploying, always pass your lane (or set `BUNDLE_VAR_lane=pattern_NN` in your environment):

```
databricks bundle deploy --target dev --var lane=pattern_NN
databricks bundle run <job_key> --target dev --var lane=pattern_NN
```

* `pytest tests/unit` needs Spark (`databricks-connect` or `pyspark`); tests marked `spark` are skipped without it.
* A failed test blocks review. A `UserWarning` in the summary is advisory: fix it or explain it in your report.
* Never weaken, skip or edit a static test to make it pass.

## Hard rules

* Never deploy or run anything with `--target prod`. Never unpause schedules.
* **Deploy and run only if your prompt says so, and only with `--var lane=pattern_NN` for your own pattern.** The lane gives you your own dev deploy folder (`~/.bundle/talend_migration/dev/pattern_NN`), job names (`[dev <user> pattern_NN] ...`) and Snowflake schema (`MIGRATION_DEV_<user>_pattern_NN`). Without it you deploy into the shared `main` lane and overwrite whoever else is using it.
* Your Snowflake schema must exist before your first run; if a run fails because it doesn't, stop and report it - don't create schemas yourself.
* Snowflake table and procedure parameters are unqualified (`STG_ORDERS`, `SP_TRANSFORM_ORDERS`); the schema comes from `snowflake_schema`. Never hard-code `MIGRATION_DEV...`, `ETL.` or other schema names.
* No credentials, hosts or tokens in code or YAML - secret scopes only.
* Anything you can't decide from the Talend export goes in `migration/pattern_NN/components.yml` as `status: needs_input` with the question in `reason`. Don't mark it `resolved` yourself.

## When you finish

Report back:

* files changed;
* output of `pytest tests/static tests/patterns/pattern_NN` and `bundle validate`, and the run URLs if you deployed;
* every `needs_input` / `deferred` component with its reason;
* any shared change you need.

Set your pattern's rows in `migration/pattern_NN/jobs.csv` to `validating` only when the tests pass.
