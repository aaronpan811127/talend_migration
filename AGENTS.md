# AGENTS.md

Instructions for coding agents (Claude Code, Codex, Cursor, Omnigent sub-agents, ...) working in this repo. Humans: start with `README.md`.

This is a Declarative Automation Bundle that migrates Talend jobs, grouped into 13 job families (`pattern_01`..`pattern_13`), to Databricks notebooks and jobs. Snowflake stays the target and Snowflake stored procedures stay the transforms. There is no converter: each pattern is converted by hand, following the skills below.

## Your task is one pattern

You work on exactly one `pattern_NN`, named in your prompt (ask if it isn't). Other sessions may be working on other patterns, or may have worked on yours before you.

**The rules live in one place:** [conventions.md](.claude/skills/talend-pattern-migration/references/conventions.md). This file only says where to start and how to map the Genie Code skills to your tools. If anything here seems to disagree with conventions.md, conventions.md wins.

The skills live in `.claude/skills/`. Claude harnesses (Claude Code, and Omnigent sessions on a Claude harness) discover them on their own when the session starts in the repo clone: load `talend-pattern-migration` or `talend-migration-validation` by name and read their `references/` files on demand. Other harnesses (Codex, Cursor, ...) don't discover them - read the files at the paths below.

Read, in this order:

1. [conventions.md](.claude/skills/talend-pattern-migration/references/conventions.md) - **before changing anything.**
2. `.claude/skills/talend-pattern-migration/SKILL.md` - the migration steps. Written for Genie Code; tool names are mapped below.
3. `.claude/skills/talend-pattern-migration/references/component-mapping.md` and `.claude/skills/talend-pattern-migration/references/notebook-template.md`.
4. `.claude/skills/talend-migration-validation/SKILL.md` - only when asked to validate.

## Start of a session

1. Clone into your sandbox; never edit the reference Git folder or use `git worktree` ([Working copy](.claude/skills/talend-pattern-migration/references/conventions.md#working-copy)): `git clone https://github.com/aaronpan811127/talend_migration ~/talend_migration`.
2. Continue the pattern's open branch, or create one ([Branches](.claude/skills/talend-pattern-migration/references/conventions.md#branches)). If another session is still on it, stop and report.
3. Run the resume procedure and report a short state summary ([Resuming and handing over](.claude/skills/talend-pattern-migration/references/conventions.md#resuming-and-handing-over)).

## While you work

* Change only your pattern's files ([Ownership](.claude/skills/talend-pattern-migration/references/conventions.md#ownership-avoids-merge-conflicts)). A shared change goes on its own shared branch and PR, only if the pattern can't be delivered without it, with unit tests ([PRs](.claude/skills/talend-pattern-migration/references/conventions.md#prs)).
* Use the scripts listed in each skill's `## Scripts` section; they live in `.claude/skills/<skill>/scripts/`. Logic other patterns could reuse becomes a script there, on a shared branch only ([Reusable scripts](.claude/skills/talend-pattern-migration/references/conventions.md#reusable-scripts)).
* After each step, update `migration/pattern_NN/checkpoint.yml` ([Checkpoint](.claude/skills/talend-pattern-migration/references/conventions.md#checkpoint)) and record decisions in `spec.md` ([Decisions](.claude/skills/talend-pattern-migration/references/conventions.md#decisions)).
* Before every push: `pytest tests/static tests/patterns/pattern_NN`.

## Before you stop

Finished, blocked or out of time: hand over ([Resuming and handing over](.claude/skills/talend-pattern-migration/references/conventions.md#resuming-and-handing-over)) - commit even half-done work, update the checkpoint with your `sessions` entry (session id from your prompt), push - then open or update the PRs and check CI ([PRs](.claude/skills/talend-pattern-migration/references/conventions.md#prs)).

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

Repeated here on purpose - they are the ones that cause damage when missed. Details in conventions.md.

* Only your pattern's files: `notebooks/pattern_NN/`, `resources/jobs/pattern_NN_*.job.yml`, `migration/pattern_NN/`, `tests/patterns/pattern_NN/`. Everything else is shared.
* Every PR targets `main`. Never push to `main`, force-push, rebase pushed commits, delete branches, or approve or merge PRs.
* Never deploy or run anything with `--target prod`. Never unpause schedules.
* **Deploy and run only if your prompt says so, and only with `--var lane=pattern_NN`** ([Deploying](.claude/skills/talend-pattern-migration/references/conventions.md#deploying)). Without it you deploy into the shared `main` lane and overwrite whoever else is using it.
* Your Snowflake schema must exist before your first run; if a run fails because it doesn't, stop and report it - don't create schemas yourself.
* Snowflake table and procedure parameters are unqualified (`STG_ORDERS`, `SP_TRANSFORM_ORDERS`); the schema comes from `snowflake_schema` ([Snowflake in dev](.claude/skills/talend-pattern-migration/references/conventions.md#snowflake-in-dev)). Never hard-code `MIGRATION_DEV...`, `ETL.` or other schema names.
* No credentials, hosts or tokens in code or YAML - secret scopes only.
* Anything you can't decide from the Talend export goes in `migration/pattern_NN/components.yml` as `status: needs_input` with the question in `reason`. Don't mark it `resolved` yourself.

## When you finish

Report back:

* your branches and PR URLs, which PR depends on which (merge order), or why you couldn't push or open them;
* the checkpoint you committed (`step`, `next`, your `sessions` entry) and the decisions you added;
* files changed;
* output of `pytest tests/static tests/patterns/pattern_NN` and `bundle validate`, and the run URLs if you deployed;
* every `needs_input` / `deferred` component with its reason;
* any shared change you need.

Set your pattern's rows in `migration/pattern_NN/jobs.csv` to `validating` only when the tests pass.
