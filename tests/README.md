# Tests

```
tests/
├── conftest.py        # `spark` fixture (Databricks runtime -> Databricks Connect -> local pyspark, else skip)
├── project.py         # shared helpers: paths, project rules, notebook / YAML readers
├── run_tests          # notebook: runs pytest on Databricks compute
├── unit/operators/    # unit tests for src/operators (shared, platform owner reviews)
├── patterns/pattern_NN/  # tests owned by the pattern owner
└── static/            # static checks on code and configs, no Spark, no deploy
```

## Running

* On Databricks: open `tests/run_tests`, set `scope` (`tests`, `tests/static`, `tests/patterns/pattern_NN`) and run it.
* Locally or in CI, from the bundle root: `pip install -r requirements-dev.txt`, then `pytest tests/static` (no Spark needed) or `pytest` (Spark tests use Databricks Connect, or are skipped without Spark).
* Run `pytest tests/static` before every PR, and alongside `databricks bundle validate --strict --target dev`.

## Static tests (`tests/static`)

They check every pattern automatically, so a new pattern needs no new static tests.

| File | Checks |
| --- | --- |
| `test_python_code.py` | `src/`, `tests/` and notebook cells compile; `from operators import ...` names exist; `src/` doesn't use notebook globals; no hard-coded credentials anywhere |
| `test_notebooks.py` | notebooks live in `notebooks/pattern_NN/`; overview cell; common widgets; snake_case widgets; uses operators, no direct I/O; bound SQL; warnings for literal paths, pandas/rdd, missing exit summary, TODO / [REVIEW] |
| `test_jobs.py` | file and key naming; tags; common parameter defaults; task keys, `depends_on`, no cycles; notebooks exist inside the pattern folder; `run_job_task` references; every parameter read by a widget; Snowflake table parameters unqualified, no hard-coded `MIGRATION_DEV`; schedules PAUSED |
| `test_bundle_config.py` | `databricks.yml` name, include, required variables, dev/prod targets; dev `snowflake_schema` is per developer; every `${var.x}` declared |
| `test_components.py` | `components.yml` fields and statuses; notebooks and cell titles exist; `[REVIEW]` cells tracked as manual; standard types documented in component-mapping.md; no `needs_input` once jobs are `ready_for_review` |
| `test_git_ownership.py` | branch names (`migrate/pattern_NN/<YYYYMMDD-HHMM>-<session>`, `shared/<topic>/<YYYYMMDD-HHMM>-<session>`); a migration branch changes only its pattern's files compared with the shared branch it's stacked on (else `origin/main`); warning when a shared branch touches pattern files. Skipped without git or `origin/main` |
| `test_agents_md.py` | `AGENTS.md` points to every skill and only to paths that exist; `CLAUDE.md` imports it |
| `test_migration_config.py` | per-pattern `jobs.csv` header, statuses, keys (unique across patterns), owner; jobs.csv and job files agree; `spec.md` and `validation.yml` structure; Snowflake `actual` uses `${snowflake_schema}` and doesn't point at prod |

A failed assertion blocks review. A `UserWarning` in the summary is advisory and should be explained in the PR.

## Unit tests

* `unit/operators/`: shared operators. Use fakes for Snowflake and readers/writers; mark tests that need a real DataFrame with `@pytest.mark.spark` and take the `spark` fixture.
* `patterns/pattern_NN/`: the pattern owner's tests. Keep testable logic (tMap expressions, filters, derivations) in plain Python modules next to the notebooks, such as `notebooks/pattern_NN/transforms.py`, and test them here. Add family-specific wiring checks too (see `patterns/pattern_01`).
* Name pattern test files `test_pattern_NN_*.py` so failures are easy to attribute.
