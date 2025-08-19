import json
from typing import Literal

from pydantic import BaseModel, Field, model_validator
from snowflake.core import Root
from snowflake.core.database import Database
from snowflake.core.schema import Schema
from snowflake.core.table import Table
from snowflake.core.warehouse import Warehouse


class ObjectMetadata(BaseModel):
    name: str | None = Field(
        default=None,  # We don't use name when listing objects
        description="The name of the object",
    )
    comment: str | None = Field(
        default=None, description="The description of the object"
    )

    @model_validator(mode="before")
    @classmethod
    def parse_json_string(cls, data):
        """
        Automatically parse JSON strings when creating instances.
        This allows passing either a dict or a JSON string to any ObjectMetadata subclass.
        """
        if isinstance(data, str):
            try:
                return json.loads(data)
            except json.JSONDecodeError as e:
                raise ValueError(f"Invalid JSON string: {e}")
        return data


class SnowflakeDatabase(ObjectMetadata):
    kind: Literal["PERMANENT", "TRANSIENT"] = Field(
        default="PERMANENT", description="The kind of database"
    )
    data_retention_time_in_days: int = Field(
        ge=0,
        lt=90,
        default=None,
        description="Specifies the number of days for which Time Travel actions (CLONE and UNDROP)"
        "can be performed on the database, as well as specifying the default"
        "Time Travel retention time for all schemas created in the database.",
    )

    def get_core_object(self):
        return Database.from_dict(self.__dict__)

    def get_core_path(self, root: Root):
        return root.databases


class SnowflakeSchema(ObjectMetadata):
    database_name: str = Field(description="The database the schema belongs to")
    kind: Literal["PERMANENT", "TRANSIENT"] = Field(
        default="PERMANENT", description="The kind of database"
    )
    data_retention_time_in_days: int = Field(
        ge=0,
        lt=90,
        default=None,
        description="Specifies the number of days for which Time Travel actions (CLONE and UNDROP)"
        "can be performed on the schema, as well as specifying the default"
        "Time Travel retention time for all tables created in the schema.",
    )

    def get_core_object(self):
        return Schema.from_dict(self.__dict__)

    def get_core_path(self, root: Root):
        return root.databases[self.database_name].schemas


class SnowflakeTableColumn(BaseModel):
    name: str = Field(description="The name of the column")
    datatype: str = Field(description="The data type of the column")
    nullable: bool = Field(default=None, description="Whether the column can be null")


class SnowflakeTable(ObjectMetadata):
    database_name: str = Field(description="The database the table belongs to")
    schema_name: str = Field(description="The schema the table belongs to")
    kind: Literal["PERMANENT", "TRANSIENT"] = Field(
        default="PERMANENT", description="The kind of table"
    )
    # Columns only used if creating a table
    columns: list[SnowflakeTableColumn] = Field(
        default=None, description="The columns of the table"
    )
    data_retention_time_in_days: int = Field(
        ge=0,
        lt=90,
        default=None,
        description="Specifies the retention period for the table so that Time Travel actions "
        "SELECT, CLONE, UNDROP can be performed on historical data in the table.",
    )

    def get_core_object(self):
        return Table.from_dict(self.__dict__)

    def get_core_path(self, root: Root):
        return root.databases[self.database_name].schemas[self.schema_name].tables


class SnowflakeWarehouse(ObjectMetadata):
    warehouse_type: Literal["STANDARD", "SNOWPARK-OPTIMIZED"] = Field(
        default="STANDARD", description="The type of warehouse"
    )
    warehouse_size: Literal[
        "X-SMALL",
        "SMALL",
        "MEDIUM",
        "LARGE",
        "X-LARGE",
        "2X-LARGE",
        "3X-LARGE",
        "4X-LARGE",
    ] = Field(default=None, description="The size of the warehouse")
    auto_suspend: int = Field(
        default=None,
        description="The number of minutes of inactivity before the warehouse is automatically suspended",
    )
    auto_resume: Literal["true", "false"] = Field(
        default=None, description="Whether the warehouse is automatically resumed"
    )
    initially_suspended: Literal["true", "false"] = Field(
        default=None, description="Whether the warehouse is initially suspended"
    )
    max_cluster_count: int = Field(
        default=None,
        description="Specifies the maximum number of clusters for a multi-cluster warehouse",
    )
    min_cluster_count: int = Field(
        default=None,
        description="Specifies the minimum number of clusters for a multi-cluster warehouse",
    )
    scaling_policy: Literal["STANDARD", "ECONOMY"] = Field(
        default=None,
        description="Scaling policy of warehouse, possible scaling policies: STANDARD, ECONOMY",
    )
    statement_timeout_in_seconds: int = Field(
        default=None,
        description="Object parameter that specifies the time, in seconds, after which a running SQL statement is canceled by the system",
    )

    def get_core_object(self):
        return Warehouse.from_dict(self.__dict__)

    def get_core_path(self, root: Root):
        return root.warehouses


SnowflakeClasses = [
    SnowflakeDatabase,
    SnowflakeSchema,
    SnowflakeTable,
    SnowflakeWarehouse,
]
