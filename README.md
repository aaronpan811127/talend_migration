# talend_migration

Declarative Automation Bundle for migrating Talend jobs to Databricks, wave by wave. A **wave** (`wave_NN`) is a set of Talend jobs migrated together - grouped by job pattern, by dependencies, or by any other rule that suits the work.

How the work is done - phases, Git, hand-over, Snowflake rules, review - is in the skills, and their rules in [conventions.md](.claude/skills/talend-wave-migration/references/conventions.md). This README only says what's where and how to get started.

## Layout

```
talend_migration/
├── databricks.yml          # bundle config, variables, dev/prod targets
├── AGENTS.md, CLAUDE.md    # entry point for coding agents
├── .claude/skills/         # the skills: talend-wave-migration (with conventions), talend-migration-validation
├── src/operators/          # reusable Python primitives: readers, writers, Snowflake, validation
├── notebooks/wave_NN/      # one notebook per job task; notebooks/validate_wave runs a wave's validation
├── resources/jobs/         # one job YAML per migrated Talend job
├── migration/wave_NN/      # everything else about a wave (spec, prompt, inputs, progress, validation, ...)
└── tests/                  # static, unit and per-wave tests - see tests/README.md
```

The package is named `operators` rather than `operator` so it doesn't shadow Python's built-in module.

## Getting started

* **In Genie Code:** clone the repo into your own Git folder ([Working copy](.claude/skills/talend-wave-migration/references/conventions.md#working-copy)), add the skills (Customizations > Skills > New > Add from workspace folder, pick `<your clone>/.claude/skills`), then ask Genie Code to "migrate wave_NN".
* **With a coding agent** (Omnigent, Claude Code, Codex, ...): start a session and paste the `## Prompt` block of `migration/wave_NN/prompt.md`; the agent follows `AGENTS.md`. To continue an earlier session instead, see [Resuming a previous session](.claude/skills/talend-wave-migration/references/conventions.md#resuming-a-previous-session).
* **New wave:** the migration skill sets up its files from `wave_01`. Each wave starts with an interactive preparation phase before it runs on its own ([Phases](.claude/skills/talend-wave-migration/references/conventions.md#phases)).

## Prerequisites (one-time setup)

* Snowflake secret scope (default `snowflake-dev`) with keys `account`, `user`, `password`, `role`, `warehouse`, `database`.
* A Snowflake shadow schema per developer and lane in the dev database ([Snowflake in dev](.claude/skills/talend-wave-migration/references/conventions.md#snowflake-in-dev)).
* Access to the S3 landing bucket through a Unity Catalog external location.
* Update the `CHANGE-ME` values and workspace hosts in `databricks.yml`.

Deploying (dev only, one lane per wave) and testing: [Deploying](.claude/skills/talend-wave-migration/references/conventions.md#deploying) and `tests/README.md`. Prod is deployed only from `main`, after PR review.
