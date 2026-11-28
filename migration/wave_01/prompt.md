# wave_01 session prompt

Paste the block below as the first message of a new Omnigent session (host: Sandbox). To continue an earlier session instead, fork or resume it first (conventions, Resuming a previous session), then send the same block.

Keep wave-specific instructions inside the block - whether this wave may deploy, who reviews it, anything about its jobs a session must know up front. Don't put progress here: where the wave stands is in `progress/checkpoint.yml`, which the session reads when it resumes.

The `Mode:` line follows the wave's phase (conventions, Phases). In Phase 1 (`Mode: preparation`) stay in the session and answer its questions. At the gate, replace the Mode paragraph with:

> Mode: conversion (autonomous) - convert every job in this wave from the wave folder without asking. Record low-risk choices in Decisions as agent; anything else becomes needs_input on the component - add it to blocked_on and carry on. Commit, push and open the PRs without asking.

## Prompt

```text
Work on wave_01 of https://github.com/aaronpan811127/talend_migration. Follow AGENTS.md: clone the repo, continue the wave's open `migrate/wave_01/...` branch if there is one (run the resume procedure first) or create one, use `--var lane=wave_01`. When you hand over, record your Omnigent session id (`sys_session_get_info`) and Claude Code session id in the checkpoint's `sessions` entry.

Mode: preparation (interactive) - work with me: read the Talend exports together, ask me every open question, and write each answer into the wave folder (spec.md Decisions, progress/components.yml, validation/validation.yml) until the Definition of ready in the conventions holds. Ask rather than guess. When it holds, go through it with me; set step: ready only after I confirm and sign off in Decisions.

Don't deploy.

Wave notes: wave_01 is the reference wave - its job ExampleOrdersLoad is a placeholder until the real Talend exports are in `migration/wave_01/inputs/`.
```
