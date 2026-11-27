<!-- Title: "pattern_NN: <summary>" for a migration PR, "shared: <topic>" for a shared PR. -->

## Depends on

<!-- Every PR targets main. Migration PR that merged in an unmerged shared branch: "Depends on #<shared PR> - merge that first" (its shared commits show here until then). Otherwise "None". -->
<!-- Shared PR: "Needed by #<migration PR(s)>", if any. -->

## What changed

* Pattern / topic:
* Sessions: <!-- Omnigent session names or people who worked on this branch -->
* Checkpoint: <!-- step and next from migration/pattern_NN/checkpoint.yml -->
* Summary:

## Open items

<!-- Every needs_input / deferred component from migration/pattern_NN/components.yml, with its reason. "None" if none. -->

## Checks

- [ ] `pytest tests/static tests/patterns/pattern_NN` passes (paste the summary line)
- [ ] `databricks bundle validate --strict --target dev --var lane=pattern_NN` passes
- [ ] Dev run URLs (if deployed):
- [ ] Reconciliation results (`migration/pattern_NN/validation_results.md`), if validated
- [ ] Shared PR: unit tests for changed operators; every pattern owner whose files it touches has approved

Agents open this PR; a human reviews and merges it - shared PRs before the migration PRs that depend on them.
