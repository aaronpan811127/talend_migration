# Wave notebook template

A wave is a folder `notebooks/wave_NN/` with one or more notebooks, one per job task, named `NN_<step>` in run order. `notebooks/wave_01/` (`01_extract_load`, `02_transform`) is the reference. Every notebook uses this cell order; include only the step cells that notebook needs.

Split into separate notebooks where Talend has a natural boundary: a subjob, a restart point, a step that must retry on its own, or a tRunJob child of the same wave. Keep a single notebook when the steps always run together.

| # | Cell title | Content |
| --- | --- | --- |
| 1 | Overview | `%md` title `# Wave NN - step N: <what it does>` and 1-2 sentences: flow and which Talend jobs use it |
| 2 | Install dependencies | `%pip install -q snowflake-connector-python` + `dbutils.library.restartPython()` (only if Snowflake SQL/procedures are used) |
| 3 | Parameters | `dbutils.widgets.text(...)` for every common parameter and each wave parameter this notebook uses, then `p = {k: dbutils.widgets.get(k) ...}`. Default `src_path` = `"/Workspace" + notebook_path.split("/notebooks/")[0] + "/src"` |
| 4 | Import operators | `sys.path.insert(0, p["src_path"])`, `from operators import ...`, build configs from secret scopes |
| 5..n | Extract: ... | One cell per source, using `read_*` operators |
| | Transform: ... | One cell per logical Talend step (tMap, filter, aggregate). Title names the Talend component, e.g. `Transform: tMap_1 enrich orders` |
| | Load: ... | One cell per target, using `write_*` operators |
| | Snowflake: ... | Stored procedure / SQL calls via `call_procedure` / `SnowflakeClient` |
| last | Exit with run summary | `dbutils.notebook.exit(json.dumps({...row counts, procedure results...}))`; values later tasks need go through `dbutils.jobs.taskValues.set(...)` |

## Rules

* Parameters only from widgets. No literal paths, table names, schemas or credentials elsewhere.
* Optional steps that only some jobs in the wave use are controlled by a widget (e.g. `call_procedure_enabled` = `true`/`false`), not by copying the notebook.
* Pure PySpark DataFrame API - no pandas, no `collect()` of full datasets, no `.rdd` (serverless/Spark Connect compatible).
* SQL sent to Snowflake uses bound parameters (`%s`), never f-strings with values.
* Count rows once per target and include them in the exit summary - validation uses them.
* Translated tJava code: cell title starts with `[REVIEW]`.
* Logic worth unit testing (complex tMap expressions, derivations) goes in a plain `.py` module in the wave folder, imported by the notebook and tested in `tests/waves/wave_NN/`.
