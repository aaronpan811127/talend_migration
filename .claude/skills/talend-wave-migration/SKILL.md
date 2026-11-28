---
name: talend-wave-migration
description: Convert one wave (wave_NN - a set of Talend jobs migrated together, grouped by job pattern, dependencies or another rule) into the talend_migration bundle - read Talend .item exports, set up the wave files, write the parameterized notebook and one job YAML per Talend job using src/operators. Read when the user asks to migrate, convert, analyze, or scaffold a Talend job or wave.
---

# Talend wave migration

You are converting **one wave** at a time inside the `talend_migration` bundle. Several people do this in parallel, each owning different waves, so you must stay inside the files that wave owns.

There is no upfront converter. A wave runs in two phases ([Phases](references/conventions.md#phases)); the checkpoint's `step` and the `Mode:` line in `prompt.md` say which one you are in:

* **Phase 1 - Preparation (interactive), Steps 0-3 and the gate.** Work with the person who started you: read the Talend exports together, ask every open question, and write each answer into the wave folder until the [Definition of ready](references/conventions.md#definition-of-ready) holds. Ask rather than guess.
* **Phase 2 - Conversion (autonomous), Steps 4-7.** Convert every job in the wave from the wave folder alone. Don't ask and don't wait: low-risk reversible choices go in `## Decisions` as `agent`; anything else becomes `needs_input` on that component, and you continue with the rest. It is capped by the [Retry limit](references/conventions.md#retry-limit).

In both phases: convert deterministically wherever you can - operators and mapping-table rows first, then scripts, and LLM-written code only where neither covers it ([Deterministic first](references/conventions.md#deterministic-first)). And report what each session used ([Cost and performance](references/conventions.md#cost-and-performance)).

Follow the conventions and mapping references below. Use the scripts listed under [Scripts](#scripts) where they fit. When logic from this wave would help other waves, make it a script in this skill's `scripts/` folder on a shared branch ([Reusable scripts](references/conventions.md#reusable-scripts)).

Read before starting:
* [references/conventions.md](references/conventions.md) - **the single source of the rules**: ownership, Git, checkpoint, decisions, resume and hand-over, Snowflake, review checklist, definition of done. **Always read.** This skill only adds the migration steps and what is specific to Genie Code; it links to conventions instead of repeating it.
* [references/component-mapping.md](references/component-mapping.md) - Talend component and Java expression to PySpark / operator mapping.
* [references/notebook-template.md](references/notebook-template.md) - required cell structure of a wave notebook.

When conversion is finished, hand off to the `talend-migration-validation` skill.

## Scripts

Reusable helpers in `scripts/` (rules: [Reusable scripts](references/conventions.md#reusable-scripts)). Run from the repo root with `python .claude/skills/talend-wave-migration/scripts/<name>.py --help`; check their output like your own work.

| Script | What it does | When to use it |
| --- | --- | --- |
| _(none yet)_ | | |

## Step 0 - Locate the project and the wave

* Bundle root (`<root>`) = the folder three levels above this skill folder (`<root>/.claude/skills/talend-wave-migration`). Confirm `<root>/databricks.yml` has `bundle.name: talend_migration`.
* Ask for the wave id (`wave_NN`, two digits) if it isn't given. Look it up in `<root>/migration/<wave>/progress/jobs.csv` to get the Talend jobs in that wave and the owner. In Phase 1, if the user is not the owner listed, tell them and stop unless they confirm. Read `step` in `progress/checkpoint.yml`: `setup`/`analyze`/`spec` = Phase 1, `ready` or later = Phase 2.
* Git follows [Working copy](references/conventions.md#working-copy), [Branches](references/conventions.md#branches) and [Resuming and handing over](references/conventions.md#resuming-and-handing-over). What is specific to Genie Code:
  * `<root>` is the user's own Git folder clone, not the reference checkout. Load the `git` skill and use `runGit` (`status`, `list_branches`, `checkout`, `pull`, `diff`, `commit_and_push`).
  * Phase 1: ask the user before creating a branch, committing or pushing. Phase 2: commit and push as in the conventions without asking, and list what you committed in your summary.
  * Genie Code can't reach GitHub: ask the user to paste PR comments during the resume.
  * Your `sessions` entry has `harness: genie-code`, `omnigent_session_id: null`, `claude_session_id: null`, `by: <user's email>`.
* Keep [the checkpoint](references/conventions.md#checkpoint) current after every step below, and record what the user decides in [Decisions](references/conventions.md#decisions).

## Step 1 - Read the Talend exports

Talend exports (`.item` files, plus optional `.properties`/`.screenshot`) go in `<root>/migration/<wave>/inputs/`. If the folder is empty, ask the user to upload the exported job(s) there.

Read each `.item` with `readAssetById` and walk through it with the developer. Record what you find directly in `spec.md` (Step 3):

* Components (`node` elements, `componentName`) and the flow between them (`connection` elements, including tRunJob children and OnSubjobOk/OnComponentOk triggers).
* Context variables (`context` / `contextParameter`) and their values per environment.
* Connections, SQL statements, Snowflake stored procedure calls and their arguments.
* tMap expressions, filters, joins and lookups.

Compare the jobs in the wave. If one has a different component flow, report it - it may belong to another wave or need an optional branch in the notebook (controlled by a parameter). Record every component in `migration/<wave>/progress/components.yml` (fields in [conventions.md](references/conventions.md#component-status-file)). Give every component a mapping and a planned implementation (`status: planned`). Anything without a clear mapping in [component-mapping.md](references/component-mapping.md) (tJava*, custom routines, unknown components) is `manual` or `unsupported` with `status: needs_input` and the question in `reason` - then ask the person, record the answer in `## Decisions`, and turn it into `planned` or `deferred`.

## Step 2 - Set up the wave files (first time only)

Skip if `<root>/notebooks/<wave>/` already exists. Never overwrite existing files. Using `wave_01` as the starting point, create:

* `notebooks/<wave>/` - one notebook per job task (`01_<step>`, `02_<step>` ...), based on the notebooks in `notebooks/wave_01/` and retitled. Decide the split from the Talend subjobs (see notebook-template.md).
* `tests/waves/<wave>/test_<wave>_*.py` - start from `tests/waves/wave_01/test_wave_01.py`.
* `resources/jobs/<wave>_<talend_job_snake>.job.yml` - one per Talend job, based on `resources/jobs/wave_01_example.job.yml`, with the job key, name and tags from conventions.
* `migration/<wave>/` - the wave folder ([Wave folder](references/conventions.md#wave-folder)), based on wave_01's with placeholders reset: `spec.md` (empty `## Decisions` table), `prompt.md` (wave id, lane and notes changed - ask the user whether the wave may deploy), `inputs/`, `progress/components.yml` and `progress/checkpoint.yml`, `validation/validation.yml`, `scripts/README.md`, `learnings/learnings.md`.
* `migration/<wave>/progress/jobs.csv` (header `talend_job,job_key,owner,status,notes`) with a row per Talend job (`status` = `analyzing`).

Show the developer the list of files before creating them.

## Step 3 - Write the spec

Fill in `migration/<wave>/spec.md` from Step 1: flow (source -> steps -> targets), parameters (common vs per job), Snowflake objects and procedures touched, variances between jobs, open questions, and the `## Decisions` table ([Decisions](references/conventions.md#decisions)). Keep it short and factual - this is what reviewers and other teammates read. Also draft `validation/validation.yml` (one check per target) and agree with the person which Talend runs validation will compare against.

## Gate - Ready for autonomous conversion (end of Phase 1)

* Go through the [Definition of ready](references/conventions.md#definition-of-ready) with the person and close what's left: every open question answered (`## Open questions` says `None`), every component `planned`, `resolved` or `deferred`, an export for every job in `inputs/`.
* Ask them to confirm, then add their sign-off row to `## Decisions` (`Ready for autonomous conversion`, decided by their email), set `step: ready` in the checkpoint, and change `prompt.md` to `Mode: conversion` (and whether it may deploy).
* Run the tests - they check the gate - then commit and push with their OK. From here on, sessions on this wave run without a person.

## Step 4 - Convert the notebook (Phase 2 - autonomous)

From here on, don't ask: decide from the wave folder, or record `needs_input` and move on ([Phases](references/conventions.md#phases)). Set `step: convert` and the jobs' status to `converting` when you start.

Read each notebook in `notebooks/<wave>/` with `readAssetById`, then edit it with `editAsset` (load the `notebook-authoring` skill first).

* Follow the cell structure in [notebook-template.md](references/notebook-template.md).
* Every Talend context variable becomes a widget and a job parameter. Every connection becomes a secret scope lookup - never hard-code credentials, hosts or passwords.
* Snowflake: build every config with `schema=p["snowflake_schema"]` and keep table parameters unqualified, so each developer's dev runs land in their own shadow schema (see [Snowflake in dev](references/conventions.md#snowflake-in-dev)).
* Use operators from `src/operators` for all I/O and Snowflake calls. Do transformations (tMap, tFilterRow, tAggregateRow ...) inline with the PySpark DataFrame API using the mapping reference.
* If an operator you need doesn't exist, **do not** write ad-hoc I/O in the notebook and do not edit `src/operators` silently. Mark the component `needs_input` with the proposed function signature in `reason` (a shared change, see conventions), and continue with the rest.
* Translate tJava/tJavaRow code to PySpark, mark the cell title with `[REVIEW]`, and record it in `components.yml` as `mapping: manual` with that `notebook` and `cell`. It stays `needs_input` until a human reviews it and you add `reviewed_by`.
* As each component is implemented, update its entry: `implementation`, `notebook`, `cell`, `status: resolved`, `converted_by` (`operator`, `script:<name>` or `llm`), and any `semantic_deltas` (behaviour that differs from Talend). Write code yourself (`llm`) only when no operator, mapping row or script fits; it is then `mapping: manual` and needs a person's review. If you write the same kind of translation a second time, propose it as a mapping row or a script. Never mark a component `resolved` on the developer's behalf if they haven't confirmed an open question.
* Do not run the notebook against Snowflake production objects. Do not change the notebook's language.

## Step 5 - Job YAMLs

One file per Talend job: `resources/jobs/<wave>_<talend_job_snake>.job.yml`, job key identical to the file stem. One task per notebook in `notebooks/<wave>/` (`notebook_path: ../../notebooks/<wave>/<NN_step>.ipynb`), chained with `depends_on` in run order. Copy the parameter values from that job's context variables (recorded in the spec). Keep the common parameters from conventions. Translate Talend scheduler/TAC triggers into `schedule` but leave `pause_status: PAUSED` until cutover. tRunJob children become extra tasks with `depends_on`, not separate notebooks, unless they are a different wave (then use `run_job_task`).

## Step 6 - Tests and review checks

* Add unit tests for this wave's helper modules and wave-specific wiring in `tests/waves/<wave>/`.
* Run the tests: run the `<root>/tests/run_tests` notebook with `scope` = `tests/static`, then `tests/waves/<wave>`. Or with `executeCode` language `python`: `sys.dont_write_bytecode = True` (`/Workspace` rejects `__pycache__` writes), `os.chdir("<root>")`, then `pytest.main(["tests/static", "tests/waves/<wave>", "-q", "-p", "no:cacheprovider"])`.
* Fix every failure. Fix each warning, or explain it in your summary and the PR description.
* Go through the parts of the review checklist in [conventions.md](references/conventions.md#review-checklist) the tests can't judge.
* Run `bundle validate --strict --target dev` with `runDatabricksCli` and `workingDirectory=<root>`.

## Step 7 - Update status and hand off

* Update `migration/<wave>/progress/jobs.csv` (`status` -> `validating`) and the checkpoint (`step: validate`, `next`).
* Hand over and open the PRs as in [Resuming and handing over](references/conventions.md#resuming-and-handing-over) and [PRs](references/conventions.md#prs). Genie Code specifics: show `runGit` `diff` first; in Phase 1 commit only with the user's OK (in Phase 2 without asking), using `commit_and_push` with `files` so each commit holds only that branch's files; instead of `gh`, give the user the compare links from [PRs](references/conventions.md#prs) with a body filled from `.github/pull_request_template.md`.
* Summarize: files changed, and every `needs_input` / `deferred` component with its reason. Then continue with the `talend-migration-validation` skill.

## Do not

* Break the Git rules in [PRs](references/conventions.md#prs) (no commits to `main`, no force-push or rebasing pushed branches, only this wave's branches).
* Edit another wave's files, `databricks.yml`, `src/operators/*`, the shared tests (`tests/static`, `tests/unit`, `tests/project.py`, `tests/conftest.py`), or the skills, unless the user explicitly says this is a shared change.
* Weaken or skip a static test to make it pass. If a rule doesn't fit your wave, raise it as a shared change.
* Deploy to `prod` or unpause schedules.
* Write to Snowflake objects that the Talend job writes in production. Dev runs must target the shadow schema set in the job parameters.
