# AGENTS.md

Instructions for coding agents (Claude Code, Codex, Cursor, Omnigent, ...) working in this repo. Humans: start with `README.md`.

This repo migrates Talend jobs to Databricks, one wave (`wave_NN`, named in your prompt) at a time. Everything about how - steps, rules, Git, hand-over - is in the skills. This file only says how to load them and how to map their tools to yours.

## Load the skills

* `.claude/skills/talend-wave-migration/SKILL.md` - migrate a wave. Start here; it tells you what to read next, including [conventions.md](.claude/skills/talend-wave-migration/references/conventions.md), the rules every session follows.
* `.claude/skills/talend-migration-validation/SKILL.md` - validate a wave, when asked.

Claude harnesses (Claude Code, Omnigent sessions on a Claude harness) discover these when the session starts in the repo clone: load them by name and read their `references/` files on demand. Other agents read the files at these paths.

## Tool mapping

Some skill steps name specific tools. Use your equivalent:

| Skill says | Do this |
| --- | --- |
| `readAssetById` | Read the file. Notebooks are `.ipynb` JSON |
| `editAsset` on a notebook | Edit the `.ipynb` JSON. Keep the notebook- and cell-level `application/vnd.databricks.v1+...` metadata; a cell's title is `metadata["application/vnd.databricks.v1+cell"]["title"]`, which the tests and `components.yml` refer to |
| `createAsset` | Create the file |
| `executeCode` language `sh` / `python` | Run it in your shell / Python |
| `runDatabricksCli` `<args>` | `databricks <args>` from the repo root |
| load the `notebook-authoring` skill | Edit the `.ipynb` as above, following `references/notebook-template.md` |
| `runGit` | `git` in your own clone |
| load the `job-run-diagnosis` skill | `databricks jobs get-run <run_id>` and `databricks jobs get-run-output <task_run_id>`; read the error and the failing cell |
| "ask the user" / "tell the user" | Phase 1 (`Mode: preparation` in the wave's `prompt.md`): ask the person in the session, or stop and report back; don't guess. Phase 2 (`Mode: conversion`): don't stop - record the question as `needs_input`, add it to `blocked_on`, continue ([Phases](.claude/skills/talend-wave-migration/references/conventions.md#phases)) |

