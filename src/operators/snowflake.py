"""Snowflake SQL / stored procedure execution (replaces Talend tSnowflakeRow / tSnowflakeSP).

Requires the `snowflake-connector-python` package on the cluster or notebook environment.
"""
import logging
import re
from typing import Any, List, Optional, Sequence

from .config import SnowflakeConfig

log = logging.getLogger(__name__)

# Allows DB.SCHEMA.PROC, optionally double-quoted parts. Blocks injection via the procedure name.
_IDENTIFIER = re.compile(r'^("[^"]+"|[A-Za-z_][A-Za-z0-9_$]*)(\.("[^"]+"|[A-Za-z_][A-Za-z0-9_$]*)){0,2}$')
_PART = re.compile(r'"[^"]+"|[A-Za-z_][A-Za-z0-9_$]*')
_SINGLE_PART = re.compile(r'^("[^"]+"|[A-Za-z_][A-Za-z0-9_$]*)$')


def qualify_name(name: str, cfg: SnowflakeConfig) -> str:
    """Fully qualify a procedure/object name with the config's database and schema.

    PROC -> <database>.<schema>.PROC and SCHEMA.PROC -> <database>.SCHEMA.PROC; DB.SCHEMA.PROC is kept.
    Unqualified names therefore always run in cfg.schema (the developer's shadow schema in dev),
    never wherever Snowflake's search path happens to find them.
    """
    if not _IDENTIFIER.match(name):
        raise ValueError(f"Invalid Snowflake object name: {name!r}")
    for label, value in (("database", cfg.database), ("schema", cfg.schema)):
        if not _SINGLE_PART.match(value or ""):
            raise ValueError(f"Invalid Snowflake {label} in config: {value!r}")
    parts = _PART.findall(name)
    prefix = {1: [cfg.database, cfg.schema], 2: [cfg.database], 3: []}[len(parts)]
    return ".".join(prefix + parts)


class SnowflakeClient:
    """Thin context-managed wrapper around snowflake.connector.

    with SnowflakeClient(cfg) as sf:
        sf.call_procedure("SP_LOAD_ORDERS", ["2026-11-24"])   # runs <database>.<cfg.schema>.SP_LOAD_ORDERS
    """

    def __init__(self, cfg: SnowflakeConfig):
        self.cfg = cfg
        self._conn = None

    def __enter__(self) -> "SnowflakeClient":
        import snowflake.connector

        self._conn = snowflake.connector.connect(**self.cfg.connector_kwargs())
        return self

    def __exit__(self, *exc) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    def execute(self, sql: str, params: Optional[Sequence[Any]] = None) -> List[tuple]:
        """Run a SQL statement with bound parameters (never format values into sql)."""
        with self._conn.cursor() as cur:
            log.info("Snowflake execute: %s", sql)
            cur.execute(sql, params)
            try:
                return cur.fetchall()
            except Exception:
                return []

    def call_procedure(self, name: str, args: Optional[Sequence[Any]] = None) -> List[tuple]:
        """CALL a stored procedure with bound arguments and return its result rows.

        Pass the name unqualified (e.g. "SP_TRANSFORM_ORDERS"); it is qualified with cfg.database and
        cfg.schema, so dev runs call the copy in the developer's shadow schema.
        """
        qualified = qualify_name(name, self.cfg)
        args = list(args or [])
        placeholders = ", ".join(["%s"] * len(args))
        result = self.execute(f"CALL {qualified}({placeholders})", args)
        log.info("Procedure %s returned %s", qualified, result)
        return result


def call_procedure(cfg: SnowflakeConfig, name: str, args: Optional[Sequence[Any]] = None) -> List[tuple]:
    """One-shot helper: open a connection, CALL the procedure, close."""
    with SnowflakeClient(cfg) as sf:
        return sf.call_procedure(name, args)
