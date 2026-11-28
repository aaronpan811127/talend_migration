<!-- Title: "wave_NN: <summary>" for a migration PR, "shared: <topic>" for a shared PR. -->

## Depends on

<!-- Every PR targets main. Migration PR that merged in an unmerged shared branch: "Depends on #<shared PR> - merge that first" (its shared commits show here until then). Otherwise "None". -->
<!-- Shared PR: "Needed by #<migration PR(s)>", if any. -->

## What changed

* Wave / topic:
* Sessions: <!-- Omnigent session names or people who worked on this branch -->
* Checkpoint: <!-- step and next from migration/wave_NN/progress/checkpoint.yml -->
* Summary:

## Open items

<!-- Every needs_input / deferred component from migration/wave_NN/progress/components.yml, with its reason. "None" if none. -->

## Checks

- [ ] `pytest tests/static tests/waves/wave_NN` passes (paste the summary line)
- [ ] `databricks bundle validate --strict --target dev --var lane=wave_NN` passes
- [ ] Dev run URLs (if deployed):
- [ ] Reconciliation results (`migration/wave_NN/validation/results.md`), if validated
- [ ] Shared PR: unit tests for changed operators; every wave owner whose files it touches has approved

Agents open this PR; a human reviews and merges it - shared PRs before the migration PRs that depend on them.
