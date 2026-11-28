# Conventions for parallel migration work

The single source for how the work is done - ownership, Git, checkpoint, hand-over, Snowflake, review. `AGENTS.md` and the skills are short entry points that link here; change procedures here, not there.

## Waves

A **wave** (`wave_NN`) is a set of Talend jobs migrated together and delivered as one migration PR. How jobs are grouped is a planning choice, recorded in each wave's `spec.md` (`## Why these jobs are one wave`): by job pattern (same flow, so one set of notebooks serves them all), by dependencies (jobs that feed each other, cut over together), by source system, by business domain, or by any other rule. Each wave has one owner and one set of notebooks; a job belongs to exactly one wave.

## Wave folder

Everything about one wave except its notebooks, job YAMLs and tests lives in `migration/wave_NN/`:

| Path | Holds | Changes |
| --- | --- | --- |
| `spec.md` | the design: why these jobs are one wave, Talend jobs in scope, flow, parameters, Snowflake objects, variances between jobs, `## Decisions`, open questions | when the design or a decision changes |
| `prompt.md` | the prompt that starts a session on this wave: one ```` ```text ```` block under `## Prompt` to paste into Omnigent, with a `Mode:` line (`preparation` in Phase 1, `conversion` from the gate on - [Phases](#phases)) and the wave's own instructions (whether it may deploy, reviewers, notes about its jobs). No progress - that is in `progress/` | at the gate, and when the wave's instructions change |
| `inputs/` | what the work starts from: Talend `.item` exports (plus `.properties`), context files, sample data | when exports are added or refreshed |
| `progress/jobs.csv` | the wave's jobs: `talend_job,job_key,owner,status,notes` ([Inventory](#inventory-migrationwave_nnprogressjobscsv)) | as jobs move through the statuses |
| `progress/checkpoint.yml` | hand-over state between sessions ([Checkpoint](#checkpoint)) | after every step and before every stop |
| `progress/components.yml` | status of every Talend component ([Component status file](#component-status-file)) | as components are resolved |
| `validation/validation.yml` | reconciliation rules: one check per target | when targets or rules change |
| `validation/results.md` | recorded results, newest last | after every validation run |
| `validation/reports/` | generated reports (diffs, exports), optional | after validation runs |
| `scripts/` | scripts only this wave needs ([Reusable scripts](#reusable-scripts)) | on the wave's migration branch |
| `learnings/learnings.md` | what this wave taught us ([Learnings](#learnings)) | whenever something is learned |

Nothing else goes at the top of the wave folder, `progress/` holds only those three files, and `validation/` only those three entries; `tests/static/test_migration_config.py` enforces the layout. The spec holds no status: status is in `progress/`, so it can't drift between files.

## Learnings

`learnings/learnings.md` is the wave's log of things worth knowing next time - a surprise in the Talend exports, a behaviour difference found in validation, an approach that didn't work and what did. It differs from `## Decisions` in the spec: a decision is a choice not to undo; a learning is knowledge to reuse.

* One entry per learning, newest last: `## YYYY-MM-DD <short title>`, a few lines on what happened and what to do instead, and a `Promoted:` line.
* **Promote what applies beyond this wave** on a shared branch: a mapping into `component-mapping.md`, a rule into these conventions, a helper into a skill script. Then set `Promoted:` to where it went (file, section or PR); otherwise `Promoted: no`.
* Add learnings as part of hand-over, like decisions. A session resuming a wave reads them after the spec.

## Phases

Every wave runs in two phases. The first is interactive and makes the wave folder complete; the second is autonomous and converts every job from it.

| Phase | Checkpoint `step` | Prompt `Mode:` | Who decides |
| --- | --- | --- | --- |
| **1 - Preparation** (interactive) | `setup`, `analyze`, `spec` | `preparation` | the session works with a person: reads the exports with them, asks every open question, records each answer in `## Decisions` |
| **Gate** | `ready` | `conversion` | a person confirms the [Definition of ready](#definition-of-ready) |
| **2 - Conversion** (autonomous) | `convert`, `job_yamls`, `tests`, `validate`, `pr_review`, `done` | `conversion` | the session, from the wave folder alone - it never waits for an answer |

**In Phase 1,** ask rather than guess: every question about Talend behaviour, Snowflake objects, parameters, grouping or validation is closed now and written down - in `spec.md` (`## Decisions`, Flow, Parameters, Snowflake objects), `progress/components.yml` (a mapping and a planned implementation for every component) and `validation/validation.yml`. Phase 1 ends when the Definition of ready holds and a person adds the sign-off row to `## Decisions`: `| <date> | Ready for autonomous conversion | <why: questions closed> | <their email> |`. Then set `step: ready` and switch `prompt.md` to `Mode: conversion`.

**In Phase 2,** don't ask and don't wait - nobody is there. Follow the wave folder and these conventions:

* A choice the wave folder doesn't cover but that is low-risk and easy to reverse: make it, and record it in `## Decisions` with `Decided by` = `agent`.
* Anything else - unclear Talend behaviour, a missing operator, a hand-translated tJava cell that needs review: mark that component `needs_input` with the question in `reason`, add it to `blocked_on`, and carry on with the other components and jobs.
* Commit, push and open the PRs as in [PRs](#prs) without asking. Stop early only if nothing else can be done, and hand over with `blocked_on` saying why.
* The person reviewing the PR answers the `needs_input` items; a later Phase 2 session picks the answers up from `## Decisions`.

### Definition of ready

Checked by `tests/static/test_migration_config.py` when `step` is `ready` (the sign-off row and the empty open questions from `ready` on):

1. `inputs/` has a Talend `.item` export for every job in `progress/jobs.csv` (file name starting with the `talend_job` name), and every row has a `job_key` and an owner.
2. `spec.md` is complete: why these jobs are one wave, Flow, Parameters, Snowflake objects, and `## Open questions` says `None`.
3. `progress/components.yml` lists every component with a mapping, and none is `needs_input`: each is `planned` (mapping and planned implementation decided), `resolved` or `deferred` with a reason.
4. `validation/validation.yml` has a check per target.
5. `prompt.md` says `Mode: conversion` and whether the session may deploy.
6. `## Decisions` has the sign-off row, decided by a person (an email).

## Ownership (avoids merge conflicts)

Each wave has exactly one owner (see `migration/wave_NN/progress/jobs.csv`). The owner, and their agent, only touch:

| Path | Owner |
| --- | --- |
| `notebooks/wave_NN/**` | wave owner |
| `resources/jobs/wave_NN_*.job.yml` | wave owner |
| `migration/wave_NN/**` | wave owner |
| `tests/waves/wave_NN/**` | wave owner |
| `src/operators/**`, `tests/unit/**`, `tests/static/**`, `tests/conftest.py`, `tests/project.py`, `pytest.ini`, `databricks.yml`, `.claude/skills/**`, `notebooks/validate_wave`, `AGENTS.md`, `CLAUDE.md`, `.gitignore`, `.github/**` | shared - platform owner reviews |

Shared changes go in their own small `shared/<topic>/...` branch and PR, separate from wave work (see PRs below), and need a unit-style test or a dev run. Adding a new function is fine; changing an existing signature needs every wave owner's sign-off.

## Git and environments

The repo is `https://github.com/aaronpan811127/talend_migration` (default branch `main`). The Git folder `/Workspace/Users/aaron.pan@databricks.com/talend_migration` is the reference checkout: read it, don't do wave work in it.

### Branches

A wave's work lives on one migration branch until its PR merges. Several sessions (Omnigent sandbox sessions, or people in Genie Code) can work on that branch one after another, handing over through the wave's checkpoint (below). After the PR merges, later work on the same wave starts a new branch.

| Branch | Name | Changes | Created from | PR into |
| --- | --- | --- | --- | --- |
| Migration | `migrate/wave_NN/<YYYYMMDD-HHMM>` | only that wave's files | `origin/main` | `main` |
| Shared | `shared/<topic>/<YYYYMMDD-HHMM>` | shared files (`src/operators`, `databricks.yml`, `.claude/skills/`, ...) | `origin/main` | `main` |

* `<YYYYMMDD-HHMM>` is when the branch was created, in **UTC** (`date -u +%Y%m%d-%H%M`). `<topic>` is a short lowercase slug, e.g. `read-files-incremental`. Example: `migrate/wave_01/20261127-1015`, which merged in `shared/read-files-incremental/20261127-1012` while that PR was open.
* **Which branch to use.** At the start of a session: `git fetch origin`, then list the wave's branches that aren't merged yet: `git branch -r --no-merged origin/main --list 'origin/migrate/wave_NN/*'`. Continue the newest one, reading its checkpoint first. Create a new branch only if there is none.
* **One active session per wave at a time.** Sessions take turns on the branch; the wave's dev lane (`--var lane=wave_NN`) and Snowflake schema are per wave too. Before starting, check the checkpoint's `updated` time and the branch's latest commit, and don't start while another session is still working on it.
* Never create a plain `migrate/wave_NN` or `shared/<topic>` branch: git can't hold both `x` and `x/...`, so one would block the whole wave or topic.
* Never commit to `main`. Everything reaches `main` through reviewed PRs.
* `tests/static/test_git_ownership.py` checks the name format and fails if a migration branch changes anything outside its wave's files, compared with `origin/main` - ignoring shared commits it merged in from a `shared/...` branch.

### Working copy

Each session works in a clone that only it uses - in an Omnigent sandbox, e.g. `git clone https://github.com/aaronpan811127/talend_migration ~/talend_migration`; for a person in Genie Code, their own Git folder (Workspace > Create > Git folder). No `git worktree`. To continue a branch: `git switch <branch>` (tracks `origin/<branch>`), then `git pull` before making changes.

### Checkpoint

`migration/wave_NN/progress/checkpoint.yml` is the wave's progress, committed on the migration branch. A session reads it first and updates it after each step and before it stops, so the next session continues instead of starting over. It holds the current state only - commit messages are the history.

| Field | Meaning |
| --- | --- |
| `wave` | the folder's wave id |
| `branch` | the migration branch this work lives on (`migrate/wave_NN/<YYYYMMDD-HHMM>`), `null` before one exists |
| `depends_on` | `null`, or the unmerged `shared/...` branch merged into the migration branch |
| `prs` | `shared` and `migration`: PR number or URL once opened, else `null` |
| `step` | Phase 1: `setup`, `analyze`, `spec`; gate: `ready`; Phase 2: `convert`, `job_yamls`, `tests`, `validate`, `pr_review`, or `done` (every job in `jobs.csv` is `done`, e.g. after cutover) - see [Phases](#phases) |
| `updated` | `at` (UTC, `YYYY-MM-DDTHH:MMZ`) and `by` (session name or person) |
| `done` | short sentences: what is finished |
| `next` | short sentences: what the next session does first (may be empty only when `step` is `done`) |
| `blocked_on` | optional: `needs_input` components or other blockers |
| `sessions` | one entry per session that worked on the wave, oldest first, appended at hand-over - the ids let a later session be resumed or forked ([Resuming a previous session](#resuming-a-previous-session)): `omnigent_session_id` (from `sys_session_get_info`, `null` outside Omnigent), `claude_session_id` (the Claude Code session id, `null` for other harnesses), `harness` (`claude-code`, `codex`, `cursor`, `genie-code`, `manual`, ...), optional `host` (host or sandbox it ran on), `by` (person or session name), `at` (UTC hand-over time), `summary` (one line), optional `url` (link to the session in `<workspace-url>/omnigent`) |
| `notes` | optional free text |

No tooling is needed for the checkpoint: edit the YAML and commit it with the work (`wave_NN: checkpoint - <step>`). `tests/static/test_checkpoint.py` checks the fields, that `branch` and `depends_on` match the branch you're on and the shared branch merged into it, that `step` agrees with `jobs.csv`, that PRs are recorded from `pr_review` on, that `sessions` entries are complete and in time order, and warns when a `needs_input` component is missing from `blocked_on`.

### Decisions

Every choice a later session or reviewer must not undo goes in the `## Decisions` table of `migration/wave_NN/spec.md`, one row each, newest last: `| Date | Decision | Why | Decided by |` (date `YYYY-MM-DD`; `Decided by` = the person, or `agent` if the agent chose and nobody objected). Examples: how a tMap reject is implemented, which audit columns validation ignores, an answer the Snowflake owner gave. Chat is not a record - if it isn't in the table, the next session doesn't know it. Questions that still need an answer stay in `components.yml` (`needs_input`) or the spec's Open questions until decided, then move here.

### Resuming and handing over

A new session gets nothing from earlier sessions except what was pushed. It never sees their chat, sandbox files or uncommitted work.

**Resume (start of every session),** in this order, before changing anything:

1. `git fetch origin`; find the wave's open branch (see Branches); `git switch` to it and `git pull`.
2. `migration/wave_NN/progress/checkpoint.yml`: `step`, `next`, `blocked_on`, and the last `sessions` entries.
3. `git log --oneline origin/main..HEAD` - what earlier sessions changed (plus any shared commits merged in from `depends_on`).
4. `spec.md`, especially `## Decisions` and Open questions, then `learnings/learnings.md`.
5. `progress/components.yml`: every `needs_input` and `deferred` item.
6. `validation/results.md`, if it exists.
7. Review feedback on the open PRs (`prs` in the checkpoint): `gh pr view <n> --comments`, plus `gh pr checks <n>`.
8. Summarize the state in a few lines (where it stands, what you'll do next, what's blocked) - as your first report, or to the user in Genie Code - then continue from `next`. Don't redo or reverse anything listed in `done` or `## Decisions` without saying why.

**Hand over (before every stop, including when blocked or out of time):**

1. Commit what you have, even half done: `wave_NN: WIP <what>` - never leave work uncommitted.
2. Update the checkpoint: `step`, `done`, `next` (concrete: file, cell or check, and what's left), `blocked_on`, `updated`, and append your `sessions` entry:
   ```yaml
   - omnigent_session_id: <sys_session_get_info with no arguments -> your session id, e.g. conv_...; null outside Omnigent>
     claude_session_id: <your Claude Code session id; null for other harnesses>
     harness: <claude-code | codex | cursor | genie-code | manual>
     host: <host or sandbox you ran on, from sys_session_get_info; optional>
     by: <session name or person>
     at: <UTC now, YYYY-MM-DDTHH:MMZ>
     summary: <one line: what this session did and where it stopped>
   ```
3. Add any decision you made or were given to `## Decisions`, and anything you learned to `learnings/learnings.md` ([Learnings](#learnings)).
4. Run `pytest tests/static tests/waves/wave_NN`, push, and open or update the PRs (below).

### Resuming a previous session

For people starting the next session. A fresh session plus the resume procedure is the default - the repo carries the state. When the last session stopped in the middle of something whose reasoning matters (a half-finished tMap translation, a debugging thread), continue its conversation instead, using the ids in the checkpoint's last `sessions` entry:

| Ids recorded | How to continue | Where it works |
| --- | --- | --- |
| `omnigent_session_id` | `omnigent run --fork <omnigent_session_id>` - a new session that starts from the old conversation | anywhere you are signed in to the workspace; you need access to that session (your own, or shared with you) |
| `claude_session_id` | `claude --resume <claude_session_id>` - Claude Code reopens that conversation | only on the `host` it ran on, because Claude Code keeps its transcripts on that machine; a different sandbox can't resume it |

Either way the old conversation doesn't know about later pushes, so the continued session still runs the resume procedure first, and appends its own `sessions` entry at hand-over. Agents don't resume or fork other sessions themselves.

### PRs

Every PR targets `main` - no stacking. A wave is delivered as one migration PR, plus a separate shared PR if it needs shared changes. The agent creates the PRs; a human reviews and merges them.

1. **Shared change needed?** Create the shared branch from `origin/main`, commit only shared files (`shared: <what>`), push, open PR **shared -> `main`** titled `shared: <topic>`.
2. **Migration branch.** Create it from `origin/main`, commit only the wave's files (`wave_NN: <what>`), push, open PR **migrate -> `main`** titled `wave_NN: <summary>`.
3. **Depending on an unmerged shared change.** To build on it before it's merged, `git merge` the shared branch into the migration branch (merge, never rebase pushed branches), set `depends_on` in the checkpoint, and put "Depends on #<shared PR> - merge that first" at the top of the migration PR. Until the shared PR merges, the migration PR's diff also shows the shared commits; reviewers review those in the shared PR. If the shared branch changes again, merge it in again.
4. **Review fixes.** Push more commits to the same branch.
5. **After a shared PR merges,** merge `origin/main` into the migration branch, set `depends_on: null`, rerun the tests and push - the shared commits drop out of the migration PR's diff.
6. **PR description** (`.github/pull_request_template.md`): what it depends on, open `needs_input` / `deferred` components, test output, dev run URLs, reconciliation results.
7. **Checkpoint.** Record each new branch (`branch`, `depends_on`) and PR (`prs`) in `checkpoint.yml` as soon as it exists. Once the PRs are open, `step` stays `pr_review` while review fixes are pushed; merging is what finishes the branch (git and GitHub show it), so nobody commits to it afterwards.
8. **CI.** After opening or updating a PR, check it with `gh pr checks <n>` and fix a red check before reporting done.

Commands (an agent in a sandbox clone; Genie Code does the same with `runGit` and compare links):

```
TS=$(date -u +%Y%m%d-%H%M)
git switch -c shared/<topic>/$TS origin/main          # only if shared files must change
git add <shared files> && git commit -m "shared: <what>" && git push -u origin HEAD
gh pr create --base main --title "shared: <topic>" --body-file <filled .github/pull_request_template.md>

git switch -c migrate/wave_NN/$TS origin/main       # or: git switch <open branch> && git pull
git merge shared/<topic>/$TS                            # only if you need the unmerged shared change
git add notebooks/wave_NN migration/wave_NN tests/waves/wave_NN resources/jobs/wave_NN_*.job.yml
git commit -m "wave_NN: <what>" && git push -u origin HEAD
gh pr create --base main --title "wave_NN: <summary>" --body-file <filled template>   # "Depends on #<shared PR>" first if merged in
gh pr checks <n>
```

Rules:

* Commit small; stage only the files that belong on the branch (never `git add -A` blindly); run `pytest tests/static tests/waves/wave_NN` before every push.
* Pull before you start and push before you stop, so the next session sees your work.
* Push only your wave's branches (and their shared branch). No force-push, no rebasing pushed commits, no deleting branches. Agents create PRs but never approve or merge them.
* Staying current: `git fetch origin && git merge origin/main` (and merge the shared branch in again after it changes). Resolve conflicts in your wave's files; stop and report conflicts in shared files you didn't change.
* Creating PRs from a sandbox needs the `gh` CLI (or the GitHub API) with GitHub credentials provided by the session - never stored in the repo. Without them, push what you can and report the branch names and compare links: `https://github.com/aaronpan811127/talend_migration/compare/main...<branch>?expand=1`.

### Deploying

* Deploy only with `--target dev`. Each deploy goes into a **lane** (bundle variable `lane`): its own folder `~/.bundle/talend_migration/dev/<lane>` (so its own state and deployment lock), job-name prefix `[dev <user> <lane>]` and Snowflake schema. People use the default lane `main`. Anything that deploys in parallel under the same identity - Omnigent sub-agents, several terminals, CI jobs - passes `--var lane=wave_NN` (or sets `BUNDLE_VAR_lane`), one lane per wave.
* Lanes isolate deploys, jobs and Snowflake data; each session's own clone isolates source. A deploy from a sandbox clone uploads that clone's files to the lane's folder; a deploy from a workspace Git folder runs that folder's files in place. Either way, jobs run exactly what's in your working copy, committed or not.
* Prod deploys happen from `main` through CI or the platform owner, never from a wave branch.

## Naming

* Wave id: `wave_NN` (two digits, numbered in the order waves are planned).
* Notebooks: one folder per wave, `notebooks/wave_NN/`, holding one or more notebooks named `NN_<step>` in run order (e.g. `01_extract_load`, `02_transform`). Each notebook is one job task.
* Helper modules: plain `.py` files in the same folder (e.g. `transforms.py`) for logic you want to unit test.
* Job file / key: `resources/jobs/wave_NN_<talend_job_snake>.job.yml`, key `wave_NN_<talend_job_snake>`, `name` same as key.
* Tags on every job: `source: talend`, `wave: wave_NN`, `talend_job: <original Talend job name>`.

## Parameters

Common job parameters (every job, same names):

| Name | Value |
| --- | --- |
| `job_name` | job key |
| `src_path` | `${workspace.file_path}/src` |
| `catalog`, `schema` | `${var.catalog}`, `${var.schema}` |
| `snowflake_secret_scope` | `${var.snowflake_secret_scope}` |
| `snowflake_schema` | `${var.snowflake_schema}` |

Wave-specific parameters: snake_case versions of the Talend context variable names. Job parameters are passed to every task. Every notebook declares the common widgets plus the wave parameters it uses; every job parameter must be read by at least one of the job's notebooks.

## Snowflake in dev

* Each developer and lane has its own shadow schema, `MIGRATION_DEV_<short_name>_<lane>` (bundle variable `snowflake_schema`, from `${workspace.current_user.short_name}` and `${var.lane}`; `aaron.pan@...` gets `MIGRATION_DEV_aaron_pan_main`, and with `--var lane=wave_01` `MIGRATION_DEV_aaron_pan_wave_01`). Parallel dev runs never overwrite each other's tables.
* Snowflake table **and procedure** parameters are **unqualified** (`STG_ORDERS`, `SP_TRANSFORM_ORDERS`, not `DEV_DB.X.STG_ORDERS` or `ETL.SP_...`). `call_procedure` qualifies an unqualified name as `<database>.<snowflake_schema>.<name>`, so each developer calls the copy in their own schema and Snowflake's search path never picks a shared one. Notebooks build `SnowflakeConfig.from_secrets(..., schema=p["snowflake_schema"])`, so unqualified names resolve in the shadow schema in dev and in the prod schema in prod. Never hard-code `MIGRATION_DEV...` in code or YAML.
* In `validation.yml`, Snowflake `actual` datasets reference `${snowflake_schema}` (e.g. `DEV_DB.${snowflake_schema}.STG_ORDERS`); `validate_wave` fills it from its `snowflake_schema` widget.
* Each shadow schema must exist before its first dev run: ask the Snowflake admin to create them (one per developer and lane in use), or to grant CREATE SCHEMA on the dev database.
* Stored procedures: each shadow schema needs its own copy of every procedure the wave calls, and that copy must use unqualified table names or `CURRENT_SCHEMA()` - a body that hard-codes `ETL.` still writes shared tables. Until the Snowflake owner confirms this, keep the component `needs_input` in `components.yml`. In prod, set `snowflake_schema` to the schema the procedures live in.

## Inventory (`migration/wave_NN/progress/jobs.csv`)

One file per wave, owned by the wave owner, with columns `talend_job,job_key,owner,status,notes` (the wave is the folder). Create the wave folder ([Wave folder](#wave-folder)) with a header-only `progress/jobs.csv` when a wave is claimed. Rules: `job_key` starts with the folder's wave id; `talend_job` and `job_key` are unique across all waves; every job YAML is listed in its own wave's file. For a project-wide view, read all of them with `inventory_rows()` in `tests/project.py`.

## Status values (`jobs.csv`)

`not_started` -> `analyzing` -> `converting` -> `validating` -> `ready_for_review` -> `done` (or `blocked`, with a note).

## Component status file

`migration/wave_NN/progress/components.yml` records every Talend component in the wave and where it stands. It replaces the component mapping table in `spec.md`. Required once any of the wave's jobs is `converting` or later.

| Field | Required | Meaning |
| --- | --- | --- |
| `name` | yes | Talend component instance, e.g. `tMap_1` (unique) |
| `type` | yes | Talend component type, e.g. `tMap` |
| `mapping` | yes | `standard` (a row of component-mapping.md), `manual` (hand-written, e.g. tJava), `not_needed`, `unsupported` |
| `implementation` | when planned or resolved | operator call or PySpark summary (for `planned`: the plan); for `not_needed`, why |
| `notebook`, `cell` | `notebook` when a resolved `standard`/`manual` | notebook stem in `notebooks/wave_NN/` and exact cell title |
| `status` | yes | `planned` (mapping and planned implementation decided in Phase 1, not built yet), `resolved` (implemented), `needs_input` (blocked on a human answer), `deferred` (accepted gap, out of scope for now) |
| `reason` | for `needs_input` / `deferred` | the question to answer, or why it is deferred |
| `semantic_deltas` | no | sentences describing behaviour that differs from Talend (types, nulls, ordering, error handling) - reviewers read these |
| `reviewed_by` | `manual` + resolved | email of the human who reviewed the hand-written code |
| `jobs` | no | Talend jobs that use it, if not all of the wave |

Rules (`tests/static/test_components.py`): `planned` components need `implementation` (the plan) and become `resolved` once built - none may be left `planned` or `needs_input` once a job is `ready_for_review` or `done`; `unsupported` can't be `resolved`; `standard` types must appear in component-mapping.md (otherwise use `manual` or add the row as a shared change); every `[REVIEW]` cell is a `manual` component; no `needs_input` once a job is `ready_for_review` or `done`. `needs_input` and `deferred` items show as warnings on every test run.

## Reusable scripts

Conversion logic that more than one wave can use - parsing a Talend `.item` export, generating job YAMLs or `jobs.csv` rows, translating common tMap expressions, comparing outputs - lives as a script in the `scripts/` folder of the skill that uses it. There is still no upfront generic converter: scripts grow out of real wave work.

| Skill | Scripts folder | For |
| --- | --- | --- |
| `talend-wave-migration` | `.claude/skills/talend-wave-migration/scripts/` | analysing exports, generating and converting wave files |
| `talend-migration-validation` | `.claude/skills/talend-migration-validation/scripts/` | validation and reconciliation helpers |

* **Shared files.** Scripts are added or changed only on a `shared/<topic>/...` branch with its own PR ([PRs](#prs)), never on a migration branch. A migration branch that needs a new or changed script merges that shared branch in and sets `depends_on` in its checkpoint.
* **When to write one.** When a second wave needs the same logic (or obviously will).
* **Wave-only scripts** go in `migration/wave_NN/scripts/`: one-off analysis of the wave's exports, data fixes for its dev runs, helpers too specific to justify a skill. They are the wave owner's files, changed on the wave's migration branch, need the same docstring and `--help`, and should be tested in `tests/waves/wave_NN/`. When a second wave needs one, move it to a skill's `scripts/` on a shared branch. Logic a notebook imports stays a helper module in `notebooks/wave_NN/*.py`.
* **Helpers, not autopilot.** Script output is reviewed like hand-written work; anything a script can't map is still recorded as `needs_input` in `components.yml`.
* **Interface.** Python 3.12 standard library plus `requirements-dev.txt` (or a POSIX shell script). A command-line tool with `argparse` and `--help`; reads only the paths it is given; writes only to an output path it is given (default: stdout) and supports `--dry-run` when it writes files; no credentials, no prod targets, no Spark or Databricks calls unless its docstring says so.
* **Docstring.** The module docstring says what it does, its inputs and outputs, and a `Usage:` example.
* **Discoverable.** Listed in the `## Scripts` section of its skill's `SKILL.md` (file name, one line, when to use it). Run from the repo root: `python .claude/skills/<skill>/scripts/<name>.py --help`; with a skill loader, the script is inside that skill's own folder.
* **Tested.** A unit test in `tests/unit/scripts/test_<script name>.py` (Python scripts).

`tests/static/test_scripts.py` enforces the location (no `.py`/`.sh` files elsewhere in the repo except `src/`, `tests/`, `notebooks/`, skill `scripts/` and wave `scripts/` folders), the docstring and a working `--help` for every script, and the `SKILL.md` listing and unit test for skill scripts; `test_git_ownership.py` keeps skill scripts off migration branches.

## Tests

* `pytest tests/static` checks code and configs for every wave (no Spark). Run it on Databricks with the `tests/run_tests` notebook (`scope` = `tests/static`) or locally/CI with `pip install -r requirements-dev.txt`.
* Put wave-specific unit tests in `tests/waves/wave_NN/test_wave_NN_*.py` (see `tests/README.md`).
* Shared operator changes need unit tests in `tests/unit/operators/`; skill scripts need them in `tests/unit/scripts/` ([Reusable scripts](#reusable-scripts)).

## Review checklist

`tests/static` enforces the (must) items automatically; a failing test blocks review. Non-must items show as pytest warnings - fix them or explain them in the PR. Read the files for anything the tests can't judge (logic matches Talend, spec complete).

Each notebook in `notebooks/wave_NN/`:
* (must) First cell is the markdown overview; cell structure follows `notebook-template.md`.
* (must) Has widgets for all common parameters, and imports from `operators` for all I/O and Snowflake calls - no direct `spark.read`, `.write`, or Snowflake connector use.
* (must) No hard-coded credentials, hosts or passwords - secret scope lookups only.
* (must) No f-string or concatenated SQL passed to `execute`, `call_procedure` or `spark.sql` - use bound parameters.
* No literal `s3://` or `/Volumes/` paths - make them parameters.
* No pandas, `toPandas()` or `.rdd` on large data.
* Ends with `dbutils.notebook.exit` and a run summary (row counts).
* No leftover `TODO`; `[REVIEW]` cells are `manual` entries in `components.yml`.

Each job YAML `resources/jobs/wave_NN_*.job.yml`:
* (must) Defines exactly one job whose key equals the file stem; `name` equals the key.
* (must) Tags `source: talend`, `wave: wave_NN`, `talend_job: <original name>`.
* (must) Every `notebook_task` points at an existing notebook inside `notebooks/wave_NN/`; task keys are unique and `depends_on` has no unknown tasks or cycles.
* (must) Has all common parameters with their standard defaults, and every parameter is read by a widget in one of its notebooks.
* Any `schedule` has `pause_status: PAUSED`.

Wave folder and inventory:
* (must) `components.yml` follows the component status rules.
* (must) `spec.md` and `validation.yml` exist; `validation.yml` has at least one check, each with `expected.type` and `actual.type`.
* Talend `.item` exports are in `migration/wave_NN/inputs/`.
* (must) Every job file has a row in its wave's `jobs.csv` with the same `job_key`, and vice versa.
* (must) Snowflake table and procedure parameters are unqualified; notebooks pass `schema=p["snowflake_schema"]`; `validation.yml` Snowflake `actual` datasets use `${snowflake_schema}`.

## Definition of done for a wave

1. `spec.md` complete, no unresolved Open questions; `components.yml` has no `needs_input`, and every `deferred` item is agreed with the reviewer.
2. `pytest tests/static tests/waves/wave_NN` passes; `bundle validate --strict --target dev` passes.
3. Every job in the wave ran successfully in dev.
4. `validation.yml` reconciliation PASS for every job on at least one representative load (ideally 2-3 different business dates), recorded in `validation/results.md`.
5. The wave's PRs (its shared PR, if any, first; then the migration PR) are reviewed and merged to `main` by a human; the merged `checkpoint.yml` shows `step: pr_review` with both PRs recorded.
