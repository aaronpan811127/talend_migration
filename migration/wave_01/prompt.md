# wave_01 session prompt

Paste the block below as the first message of a new Omnigent session (host: Sandbox). To continue an earlier session instead, fork or resume it first (conventions, Resuming a previous session), then send the same block.

Keep wave-specific instructions inside the block - whether this wave may deploy, who reviews it, anything about its jobs a session must know up front. Don't put progress here: where the wave stands is in `progress/checkpoint.yml`, which the session reads when it resumes.

## Prompt

```text
Work on wave_01 of https://github.com/aaronpan811127/talend_migration. Follow AGENTS.md: clone the repo, continue the wave's open `migrate/wave_01/...` branch if there is one (run the resume procedure first) or create one, use `--var lane=wave_01`. When you hand over, record your Omnigent session id (`sys_session_get_info`) and Claude Code session id in the checkpoint's `sessions` entry.

Don't deploy.

Wave notes: wave_01 is the reference wave - its job ExampleOrdersLoad is a placeholder until the real Talend exports are in `migration/wave_01/inputs/`.
```
