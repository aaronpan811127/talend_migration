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

Everything else is shared: `src/operators/`, `tests/static/`, `tests/unit/`, `tests/project.py`, `tests/conftest.py`, `pytest.ini`, `databricks.yml`, `skills/`, `notebooks/validate_pattern`, `AGENTS.md`, `.gitignore`, `.github/`. Make shared changes only on a shared branch (below), never on your migration branch, and only when the pattern can't be delivered without them (for example a missing operator). Keep them minimal and add unit tests in `tests/unit/`.

## Git

The repo is `https://github.com/aaronpan811127/talend_migration`, default branch `main`.

Full rules: `skills/talend-pattern-migration/references/conventions.md`, section Git and environments.

1. **Your own clone and branches.** Don't edit the reference Git folder `/Workspace/Users/aaron.pan@databricks.com/talend_migration`, don't use `git worktree`, and don't share a clone with another session. Clone into the sandbox and name your branches after this session:
   ```
   git clone https://github.com/aaronpan811127/talend_migration ~/talend_migration && cd ~/talend_migration
   TS=$(date -u +%Y%m%d-%H%M)              # session start, UTC
   SESSION=<this session's name, lowercase, non a-z0-9 -> "-", max 40 chars>
   MIGRATE=migrate/pattern_NN/$TS-$SESSION
   SHARED=shared/<topic>/$TS-$SESSION     # only if you need a shared change
   ```
   Never create or push a plain `migrate/pattern_NN` or `shared/<topic>` branch.
2. **Shared change first (if needed):** `git switch -c $SHARED origin/main`, commit only shared files (`shared: <what>`), push, then `gh pr create --base main --head $SHARED --title "shared: <topic>" --body-file <filled .github/pull_request_template.md>`.
3. **Migration branch:** `git switch -c $MIGRATE $SHARED` (or `origin/main` if there is no shared change). Commit small with `pattern_NN: <what>`; stage only your pattern's files, never `git add -A` blindly. Push, then `gh pr create --base $SHARED --head $MIGRATE --title "pattern_NN: <summary>"` (base `main` if no shared branch), with "Stacked on #<shared PR>" at the top of the body.
4. **Need a shared change later?** Create `$SHARED` from `origin/main` and open its PR, then `git merge $SHARED` into `$MIGRATE` and `gh pr edit <migration PR> --base $SHARED`. Merge, never rebase.
5. **Before every push** run `pytest tests/static tests/patterns/pattern_NN`. `tests/static/test_git_ownership.py` fails if the migration branch changes anything outside your pattern (compared with the shared branch below it) or if a branch name is wrong.
6. **Never** push to `main`, force-push, rebase pushed commits, delete other sessions' branches, or approve or merge PRs - a human merges, bottom of the stack first. If `gh` or GitHub credentials are missing, push what you can and report the branch names and the compare URLs (`https://github.com/aaronpan811127/talend_migration/compare/<base>...<head>`).
7. **Staying current:** `git fetch origin`, then `git merge origin/main` into your top branch (or merge `$SHARED` into `$MIGRATE` after changing it). Resolve conflicts in your pattern's files; stop and report conflicts in shared files you didn't change.

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

* your branches, PR URLs and stack order (shared PR -> migration PR), or why you couldn't push or open them;
* files changed;
* output of `pytest tests/static tests/patterns/pattern_NN` and `bundle validate`, and the run URLs if you deployed;
* every `needs_input` / `deferred` component with its reason;
* any shared change you need.

Set your pattern's rows in `migration/pattern_NN/jobs.csv` to `validating` only when the tests pass.
