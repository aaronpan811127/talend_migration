"""Connection configuration helpers. Credentials always come from Databricks secrets."""
from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class SnowflakeConfig:
    account: str          # e.g. xy12345.us-east-1
    user: str
    password: str
    role: str
    warehouse: str
    database: str
    schema: str = "PUBLIC"

    @classmethod
    def from_secrets(cls, dbutils, scope: str, schema: Optional[str] = None) -> "SnowflakeConfig":
        """Load config from a secret scope with keys: account, user, password, role, warehouse, database."""
        get = lambda key: dbutils.secrets.get(scope=scope, key=key)
        return cls(
            account=get("account"),
            user=get("user"),
            password=get("password"),
            role=get("role"),
            warehouse=get("warehouse"),
            database=get("database"),
            schema=schema or "PUBLIC",
        )

    def spark_options(self) -> dict:
        """Options for the built-in Spark Snowflake connector (format('snowflake'))."""
        return {
            "sfUrl": f"{self.account}.snowflakecomputing.com",
            "sfUser": self.user,
            "sfPassword": self.password,
            "sfRole": self.role,
            "sfWarehouse": self.warehouse,
            "sfDatabase": self.database,
            "sfSchema": self.schema,
        }

    def connector_kwargs(self) -> dict:
        """kwargs for snowflake.connector.connect (used for SQL / stored procedures)."""
        return {
            "account": self.account,
            "user": self.user,
            "password": self.password,
            "role": self.role,
            "warehouse": self.warehouse,
            "database": self.database,
            "schema": self.schema,
        }


@dataclass(frozen=True)
class JdbcConfig:
    url: str
    user: str
    password: str
    driver: Optional[str] = None

    @classmethod
    def from_secrets(cls, dbutils, scope: str, prefix: str = "") -> "JdbcConfig":
        """Load config from keys <prefix>url, <prefix>user, <prefix>password[, <prefix>driver]."""
        get = lambda key: dbutils.secrets.get(scope=scope, key=f"{prefix}{key}")
        try:
            driver = get("driver")
        except Exception:
            driver = None
        return cls(url=get("url"), user=get("user"), password=get("password"), driver=driver)
