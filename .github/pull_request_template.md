<!-- Title: "pattern_NN: <summary>" for a migration PR, "shared: <topic>" for a shared PR. -->

## Stack

<!-- Migration PR stacked on a shared PR: "Stacked on #<shared PR>" (base = that shared branch). Otherwise "Base: main". -->
<!-- Shared PR: "Needed by #<migration PR(s)>". -->

## What changed

* Pattern / topic:
* Session: <!-- Omnigent session name or person -->
* Summary:

## Open items

<!-- Every needs_input / deferred component from migration/pattern_NN/components.yml, with its reason. "None" if none. -->

## Checks

- [ ] `pytest tests/static tests/patterns/pattern_NN` passes (paste the summary line)
- [ ] `databricks bundle validate --strict --target dev --var lane=pattern_NN` passes
- [ ] Dev run URLs (if deployed):
- [ ] Reconciliation results (`migration/pattern_NN/validation_results.md`), if validated
- [ ] Shared PR: unit tests for changed operators; every pattern owner whose files it touches has approved

Agents open this PR; a human reviews and merges it, bottom of the stack first.
