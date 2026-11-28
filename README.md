# talend_migration

Declarative Automation Bundle for migrating Talend jobs (13 job patterns) to Databricks.

## Layout

```
talend_migration/
├── databricks.yml                 # bundle config, variables, dev/prod targets
├── pytest.ini, requirements-dev.txt  # test config and local/CI test dependencies
├── AGENTS.md, CLAUDE.md           # instructions for other coding agents (Claude Code, Codex, Omnigent, ...)
├── src/operators/                 # reusable Python primitives
│   ├── config.py                  # SnowflakeConfig / JdbcConfig loaded from secret scopes
│   ├── readers.py                 # read_files (S3/Volumes), read_table, read_jdbc, read_snowflake
│   ├── writers.py                 # write_files, write_delta (append/merge), write_snowflake, write_jdbc
│   ├── snowflake.py               # SnowflakeClient, call_procedure (stored procedures, bound params)
│   └── validation.py              # compare_dataframes, run_from_config (Talend vs Databricks reconciliation)
├── notebooks/
│   ├── pattern_01/                # one folder per job family (pattern_01..pattern_13)
│   │   ├── 01_extract_load        #   one notebook per job task, in run order
│   │   └── 02_transform
│   └── validate_pattern           # runs migration/<pattern>/validation.yml
├── resources/jobs/
│   └── pattern_01_example.job.yml # one file per migrated Talend job
├── tests/                         # see tests/README.md
│   ├── run_tests                  # notebook: runs pytest on Databricks
│   ├── static/                    # static checks on code and configs (all patterns, no Spark)
│   ├── unit/operators/            # unit tests for src/operators
│   └── patterns/pattern_NN/       # tests owned by each pattern owner
├── migration/
│   └── pattern_NN/
│       ├── jobs.csv               # this pattern's inventory: Talend job -> job key -> owner -> status
│       ├── checkpoint.yml         # progress: branch, PRs, step, done, next, sessions - read first, update before stopping
│       ├── talend/                # Talend .item exports for this family
│       ├── spec.md                # flow, parameters, Snowflake objects, Decisions, open questions
│       ├── components.yml         # status of every Talend component (resolved / needs_input / deferred)
│       ├── validation.yml         # reconciliation checks
│       └── validation_results.md  # recorded results
└── .claude/skills/                # agent skills (Genie Code, and discovered by Claude Code / Omnigent Claude sessions)
    ├── talend-pattern-migration/  # read exports -> set up files -> spec -> convert -> job YAMLs -> review checklist
    │   ├── references/            # conventions, component mapping, notebook template
    │   └── scripts/               # reusable conversion scripts (shared; changed on shared branches)
    └── talend-migration-validation/  # review checklist -> dev run -> reconcile -> record
        └── scripts/               # reusable validation scripts
```

## Working in parallel

There is no upfront Talend-to-Databricks converter. Each developer works out the conversion for their own pattern with Genie Code, using the conventions, component mapping and notebook template in `.claude/skills/talend-pattern-migration/references/`. Reusable findings go back as shared changes: new operators in `src/operators/`, new mappings in the references, and reusable conversion scripts in the skills' `scripts/` folders (see Reusable scripts in the conventions).

1. Each session (an Omnigent sandbox session, or you in Genie Code) works in its own clone of `https://github.com/aaronpan811127/talend_migration` - in Omnigent inside the sandbox, in Genie Code your own Git folder; no worktrees, never a shared clone. A pattern's work lives on one branch, `migrate/pattern_NN/<YYYYMMDD-HHMM>` (UTC creation time), plus `shared/<topic>/<YYYYMMDD-HHMM>` if shared files must change. Sessions take turns on that branch and hand over through `migration/pattern_NN/checkpoint.yml`; a new branch is started only when the pattern has no open one.
2. In Genie Code, open Customizations > Skills > New > Add from workspace folder and pick `<your clone>/.claude/skills`. Both skills then load automatically. Claude harnesses (Claude Code, and Omnigent sessions on a Claude harness started in the repo clone) discover `.claude/skills` on their own and load the skills on demand; any other agent (Codex, Cursor, ...) reads `AGENTS.md`, which points to the same files.
3. Claim your pattern by creating `migration/pattern_NN/jobs.csv` (one file per pattern, so owners never conflict), put the Talend exports in `migration/pattern_NN/talend/`, and ask Genie Code to "migrate pattern_NN".
4. The migration branch changes only your pattern's files - `tests/static/test_git_ownership.py` fails it otherwise. Changes to `src/operators`, `databricks.yml`, `.claude/skills/` or other shared files go on the pattern's shared branch, with its own PR; the migration branch merges it in if it needs it before it's merged. See `skills/talend-pattern-migration/references/conventions.md` (Git and environments).
5. Run `tests/run_tests` (or `pytest tests/static tests/patterns/pattern_NN`) and fix failures before deploying.
6. Deploy with `--target dev` only. Each deploy lands in a lane (default `main`) with its own folder, job names and Snowflake schema; parallel agents add `--var lane=pattern_NN`.
7. Ask Genie Code to "validate pattern_NN". The agent pushes its branches and opens the PRs, all into `main` (no stacking): the shared PR if there is one, and the migration PR, marked "Depends on #<shared PR>" if it merged that branch in. A human reviews and merges them, shared PRs first.

### Starting an Omnigent session for a pattern

A session only knows what earlier sessions pushed. It never sees their chat or sandbox. So:

* **New or continuing pattern (default): start a fresh session** in `<workspace-url>/omnigent` (host: Sandbox) with a prompt like:
  > Work on pattern_02 of https://github.com/aaronpan811127/talend_migration. Follow AGENTS.md: clone the repo, continue the pattern's open `migrate/pattern_02/...` branch if there is one (run the resume procedure first) or create one, use `--var lane=pattern_02`. When you hand over, record your Omnigent session id (`sys_session_get_info`) and Claude Code session id in the checkpoint's `sessions` entry. Don't deploy.
* **Continuing a half-finished step whose reasoning matters:** use the ids in the last entry of `migration/pattern_02/checkpoint.yml` `sessions` - `omnigent run --fork <omnigent_session_id>` from anywhere you can access that session, or `claude --resume <claude_session_id>` on the same `host` - then send the same prompt. The continued session still runs the resume procedure, because the branch may have moved on. Details: Resuming a previous session in the conventions.
* Only one session per pattern at a time. Check the checkpoint's `updated` time before starting one.

Details: `.claude/skills/talend-pattern-migration/references/conventions.md`, sections Checkpoint, Decisions, and Resuming and handing over.

The package is named `operators` rather than `operator` so it doesn't shadow Python's built-in `operator` module.

## How it fits together

* Each **job YAML** sets job-level `parameters` (source path, target table, procedure name, and so on) and has one task per notebook in its **pattern folder**, chained with `depends_on`.
* Each **pattern notebook** reads the parameters it needs as widgets, adds `src/` to `sys.path` (`src_path` defaults to `${workspace.file_path}/src`), and chains **operators** together.
* To add a Talend job, copy a job YAML and change its parameters. To add a job family, create `notebooks/pattern_NN/` starting from the notebooks in `notebooks/pattern_01/`.

## Prerequisites

* Snowflake secret scope (default `snowflake-dev`) with keys `account`, `user`, `password`, `role`, `warehouse`, `database`.
* Your own Snowflake shadow schema `MIGRATION_DEV_<short_name>_<lane>` in the dev database (e.g. `MIGRATION_DEV_aaron_pan_main`, plus `MIGRATION_DEV_aaron_pan_pattern_NN` for each parallel agent lane). Dev jobs write there, so parallel developers and agents don't overwrite each other.
* Access to the S3 landing bucket through a Unity Catalog external location.
* Update the `CHANGE-ME` values and workspace hosts in `databricks.yml`.

## Deploy

```
pytest tests/static
databricks bundle validate --target dev
databricks bundle deploy --target dev                  # lane main
databricks bundle run pattern_01_example --target dev

# a parallel agent working on pattern_01
databricks bundle deploy --target dev --var lane=pattern_01
databricks bundle run pattern_01_example --target dev --var lane=pattern_01
```

Prod is deployed only from `main`, after PR review.
