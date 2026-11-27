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

1. **Your own clone; continue the pattern's branch if it has one.** Don't edit the reference Git folder `/Workspace/Users/aaron.pan@databricks.com/talend_migration`, don't use `git worktree`, and don't share a clone with another session. Other sessions may have worked on this pattern before you - their progress is in the branch's `migration/pattern_NN/checkpoint.yml`.
   ```
   git clone https://github.com/aaronpan811127/talend_migration ~/talend_migration && cd ~/talend_migration
   git branch -r --no-merged origin/main --list 'origin/migrate/pattern_NN/*'   # open branches for your pattern
   ```
   * **One exists:** `git switch <newest one, without origin/>`, then follow the resume procedure below. If the checkpoint's `updated.at` or the branch's latest commit is very recent, another session may still be on it - stop and report instead of working in parallel.
   * **None:** create new branches named by the current UTC time, `TS=$(date -u +%Y%m%d-%H%M)`: `MIGRATE=migrate/pattern_NN/$TS` and, only if you need a shared change, `SHARED=shared/<topic>/$TS`. Never create or push a plain `migrate/pattern_NN` or `shared/<topic>` branch.
   * **Checkpoint:** update `migration/pattern_NN/checkpoint.yml` (format in conventions, section Checkpoint) after each step and always before you stop: `branch`, `base`, `prs`, `step`, `updated` (UTC time and your session name), `done`, `next`, `blocked_on`, and your `sessions` entry. Commit it with your work and push, so the next session can pick up.
2. **Shared change first (if needed):** `git switch -c $SHARED origin/main`, commit only shared files (`shared: <what>`), push, then `gh pr create --base main --head $SHARED --title "shared: <topic>" --body-file <filled .github/pull_request_template.md>`.
3. **Migration branch:** `git switch -c $MIGRATE $SHARED` (or `origin/main` if there is no shared change). Commit small with `pattern_NN: <what>`; stage only your pattern's files, never `git add -A` blindly. Push, then `gh pr create --base $SHARED --head $MIGRATE --title "pattern_NN: <summary>"` (base `main` if no shared branch), with "Stacked on #<shared PR>" at the top of the body.
4. **Need a shared change later?** Create `$SHARED` from `origin/main` and open its PR, then `git merge $SHARED` into `$MIGRATE` and `gh pr edit <migration PR> --base $SHARED`. Merge, never rebase.
5. **Before every push** run `pytest tests/static tests/patterns/pattern_NN`. `tests/static/test_git_ownership.py` fails if the migration branch changes anything outside your pattern (compared with the shared branch below it) or if a branch name is wrong.
6. **Never** push to `main`, force-push, rebase pushed commits, delete branches, or approve or merge PRs - a human merges, bottom of the stack first. If `gh` or GitHub credentials are missing, push what you can and report the branch names and the compare URLs (`https://github.com/aaronpan811127/talend_migration/compare/<base>...<head>`).
7. **Staying current:** `git fetch origin`, then `git merge origin/main` into your top branch (or merge `$SHARED` into `$MIGRATE` after changing it). Resolve conflicts in your pattern's files; stop and report conflicts in shared files you didn't change.

## Resume and hand over

You get nothing from earlier sessions except what they pushed - not their chat, not their sandbox. Full procedure: conventions, section Resuming and handing over.

**At the start,** before changing anything, read in this order: `migration/pattern_NN/checkpoint.yml` (`step`, `next`, `blocked_on`, last `sessions` entries); `git log --oneline origin/<base>..HEAD`; `spec.md` (`## Decisions` and Open questions); `needs_input` / `deferred` items in `components.yml`; `validation_results.md` if present; PR feedback with `gh pr view <n> --comments` and `gh pr checks <n>`. Then report a short summary of the state and continue from `next`. Don't redo or reverse anything listed in `done` or `## Decisions` without saying why.

**Before you stop** - finished, blocked, or out of time:

1. Commit everything, even half done: `pattern_NN: WIP <what>`.
2. Update the checkpoint: `step`, `done`, `next` (concrete: file, cell or check, and what's left), `blocked_on`, `updated`, and append to `sessions`:
   ```yaml
   - id: <your Omnigent session id, from your prompt; else your session name>
     by: <session name or person who started you>
     at: <UTC now, YYYY-MM-DDTHH:MMZ>
     summary: <one line: what this session did and where it stopped>
   ```
3. Add every decision you made or were given to the `## Decisions` table in `spec.md`.
4. `pytest tests/static tests/patterns/pattern_NN`, then push.

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
* the checkpoint you committed (`step`, `next`, your `sessions` entry) and the decisions you added;
* files changed;
* output of `pytest tests/static tests/patterns/pattern_NN` and `bundle validate`, and the run URLs if you deployed;
* every `needs_input` / `deferred` component with its reason;
* any shared change you need.

Set your pattern's rows in `migration/pattern_NN/jobs.csv` to `validating` only when the tests pass.
