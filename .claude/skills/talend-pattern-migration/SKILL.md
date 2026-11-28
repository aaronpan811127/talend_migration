---
name: talend-pattern-migration
description: Convert one Talend job family (pattern_01..pattern_13) into the talend_migration bundle - read Talend .item exports, set up the pattern files, write the parameterized notebook and one job YAML per Talend job using src/operators. Read when the user asks to migrate, convert, analyze, or scaffold a Talend job or pattern.
---

# Talend pattern migration

You are converting **one job family (pattern)** at a time inside the `talend_migration` bundle. Several people do this in parallel, each owning different patterns, so you must stay inside the files that pattern owns.

There is no upfront converter. Each developer works out the conversion for their own pattern; help them by reading the Talend exports together and following the conventions and mapping references below. Use the scripts listed under [Scripts](#scripts) where they fit. When logic from this pattern would help other patterns, make it a script in this skill's `scripts/` folder on a shared branch ([Reusable scripts](references/conventions.md#reusable-scripts)).

Read before starting:
* [references/conventions.md](references/conventions.md) - **the single source of the rules**: ownership, Git, checkpoint, decisions, resume and hand-over, Snowflake, review checklist, definition of done. **Always read.** This skill only adds the migration steps and what is specific to Genie Code; it links to conventions instead of repeating it.
* [references/component-mapping.md](references/component-mapping.md) - Talend component and Java expression to PySpark / operator mapping.
* [references/notebook-template.md](references/notebook-template.md) - required cell structure of a pattern notebook.

When conversion is finished, hand off to the `talend-migration-validation` skill.

## Scripts

Reusable helpers in `scripts/` (rules: [Reusable scripts](references/conventions.md#reusable-scripts)). Run from the repo root with `python .claude/skills/talend-pattern-migration/scripts/<name>.py --help`; check their output like your own work.

| Script | What it does | When to use it |
| --- | --- | --- |
| _(none yet)_ | | |

## Step 0 - Locate the project and the pattern

* Bundle root (`<root>`) = the folder three levels above this skill folder (`<root>/.claude/skills/talend-pattern-migration`). Confirm `<root>/databricks.yml` has `bundle.name: talend_migration`.
* Ask for the pattern id (`pattern_NN`, two digits) if it isn't given. Look it up in `<root>/migration/<pattern>/jobs.csv` to get the Talend jobs in that family and the owner. If the user is not the owner listed, tell them and stop unless they confirm.
* Git follows [Working copy](references/conventions.md#working-copy), [Branches](references/conventions.md#branches) and [Resuming and handing over](references/conventions.md#resuming-and-handing-over). What is specific to Genie Code:
  * `<root>` is the user's own Git folder clone, not the reference checkout. Load the `git` skill and use `runGit` (`status`, `list_branches`, `checkout`, `pull`, `diff`, `commit_and_push`).
  * Ask the user before creating a branch, committing or pushing.
  * Genie Code can't reach GitHub: ask the user to paste PR comments during the resume.
  * Your `sessions` entry has `harness: genie-code`, `omnigent_session_id: null`, `claude_session_id: null`, `by: <user's email>`.
* Keep [the checkpoint](references/conventions.md#checkpoint) current after every step below, and record what the user decides in [Decisions](references/conventions.md#decisions).

## Step 1 - Read the Talend exports

Talend exports (`.item` files, plus optional `.properties`/`.screenshot`) go in `<root>/migration/<pattern>/talend/`. If the folder is empty, ask the user to upload the exported job(s) there.

Read each `.item` with `readAssetById` and walk through it with the developer. Record what you find directly in `spec.md` (Step 3):

* Components (`node` elements, `componentName`) and the flow between them (`connection` elements, including tRunJob children and OnSubjobOk/OnComponentOk triggers).
* Context variables (`context` / `contextParameter`) and their values per environment.
* Connections, SQL statements, Snowflake stored procedure calls and their arguments.
* tMap expressions, filters, joins and lookups.

Compare the jobs in the family. If one has a different component flow, report it - it may belong to another pattern or need an optional branch in the notebook (controlled by a parameter). Record every component in `migration/<pattern>/components.yml` (fields in [conventions.md](references/conventions.md#component-status-file)). Anything without a clear mapping in [component-mapping.md](references/component-mapping.md) (tJava*, custom routines, unknown components) is `manual` or `unsupported` with `status: needs_input` and the question in `reason`.

## Step 2 - Set up the pattern files (first time only)

Skip if `<root>/notebooks/<pattern>/` already exists. Never overwrite existing files. Using `pattern_01` as the starting point, create:

* `notebooks/<pattern>/` - one notebook per job task (`01_<step>`, `02_<step>` ...), based on the notebooks in `notebooks/pattern_01/` and retitled. Decide the split from the Talend subjobs (see notebook-template.md).
* `tests/patterns/<pattern>/test_<pattern>_*.py` - start from `tests/patterns/pattern_01/test_pattern_01.py`.
* `resources/jobs/<pattern>_<talend_job_snake>.job.yml` - one per Talend job, based on `resources/jobs/pattern_01_example.job.yml`, with the job key, name and tags from conventions.
* `migration/<pattern>/spec.md` (with an empty `## Decisions` table), `components.yml`, `validation.yml` and `checkpoint.yml` - based on pattern_01's, with placeholders reset.
* `migration/<pattern>/jobs.csv` (header `talend_job,job_key,owner,status,notes`) with a row per Talend job (`status` = `analyzing`).

Show the developer the list of files before creating them.

## Step 3 - Write the spec

Fill in `migration/<pattern>/spec.md` from Step 1: flow (source -> steps -> targets), parameters (common vs per job), Snowflake objects and procedures touched, variances between jobs, open questions, and the `## Decisions` table ([Decisions](references/conventions.md#decisions)). Keep it short and factual - this is what reviewers and other teammates read.

## Step 4 - Convert the notebook

Read each notebook in `notebooks/<pattern>/` with `readAssetById`, then edit it with `editAsset` (load the `notebook-authoring` skill first).

* Follow the cell structure in [notebook-template.md](references/notebook-template.md).
* Every Talend context variable becomes a widget and a job parameter. Every connection becomes a secret scope lookup - never hard-code credentials, hosts or passwords.
* Snowflake: build every config with `schema=p["snowflake_schema"]` and keep table parameters unqualified, so each developer's dev runs land in their own shadow schema (see [Snowflake in dev](references/conventions.md#snowflake-in-dev)).
* Use operators from `src/operators` for all I/O and Snowflake calls. Do transformations (tMap, tFilterRow, tAggregateRow ...) inline with the PySpark DataFrame API using the mapping reference.
* If an operator you need doesn't exist, **do not** write ad-hoc I/O in the notebook and do not edit `src/operators` silently. Tell the user it's a shared change (see conventions) and propose the function signature.
* Translate tJava/tJavaRow code to PySpark, mark the cell title with `[REVIEW]`, and record it in `components.yml` as `mapping: manual` with that `notebook` and `cell`. It stays `needs_input` until a human reviews it and you add `reviewed_by`.
* As each component is implemented, update its entry: `implementation`, `notebook`, `cell`, `status: resolved`, and any `semantic_deltas` (behaviour that differs from Talend). Never mark a component `resolved` on the developer's behalf if they haven't confirmed an open question.
* Do not run the notebook against Snowflake production objects. Do not change the notebook's language.

## Step 5 - Job YAMLs

One file per Talend job: `resources/jobs/<pattern>_<talend_job_snake>.job.yml`, job key identical to the file stem. One task per notebook in `notebooks/<pattern>/` (`notebook_path: ../../notebooks/<pattern>/<NN_step>.ipynb`), chained with `depends_on` in run order. Copy the parameter values from that job's context variables (recorded in the spec). Keep the common parameters from conventions. Translate Talend scheduler/TAC triggers into `schedule` but leave `pause_status: PAUSED` until cutover. tRunJob children become extra tasks with `depends_on`, not separate notebooks, unless they are a different pattern (then use `run_job_task`).

## Step 6 - Tests and review checks

* Add unit tests for this pattern's helper modules and family-specific wiring in `tests/patterns/<pattern>/`.
* Run the tests: run the `<root>/tests/run_tests` notebook with `scope` = `tests/static`, then `tests/patterns/<pattern>`. Or with `executeCode` language `python`: `sys.dont_write_bytecode = True` (`/Workspace` rejects `__pycache__` writes), `os.chdir("<root>")`, then `pytest.main(["tests/static", "tests/patterns/<pattern>", "-q", "-p", "no:cacheprovider"])`.
* Fix every failure. Fix or explain each warning to the user.
* Go through the parts of the review checklist in [conventions.md](references/conventions.md#review-checklist) the tests can't judge.
* Run `bundle validate --strict --target dev` with `runDatabricksCli` and `workingDirectory=<root>`.

## Step 7 - Update status and hand off

* Update `migration/<pattern>/jobs.csv` (`status` -> `validating`) and the checkpoint (`step: validate`, `next`).
* Hand over and open the PRs as in [Resuming and handing over](references/conventions.md#resuming-and-handing-over) and [PRs](references/conventions.md#prs). Genie Code specifics: show `runGit` `diff` first; commit only with the user's OK, using `commit_and_push` with `files` so each commit holds only that branch's files; instead of `gh`, give the user the compare links from [PRs](references/conventions.md#prs) with a body filled from `.github/pull_request_template.md`.
* Summarize: files changed, and every `needs_input` / `deferred` component with its reason. Then continue with the `talend-migration-validation` skill.

## Do not

* Break the Git rules in [PRs](references/conventions.md#prs) (no commits to `main`, no force-push or rebasing pushed branches, only this pattern's branches).
* Edit another pattern's files, `databricks.yml`, `src/operators/*`, the shared tests (`tests/static`, `tests/unit`, `tests/project.py`, `tests/conftest.py`), or the skills, unless the user explicitly says this is a shared change.
* Weaken or skip a static test to make it pass. If a rule doesn't fit your pattern, raise it as a shared change.
* Deploy to `prod` or unpause schedules.
* Write to Snowflake objects that the Talend job writes in production. Dev runs must target the shadow schema set in the job parameters.
