from typing import Literal

from pydantic import BaseModel, Field
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


class SnowflakeDatabase(ObjectMetadata):
    kind: Literal["PERMANENT", "TRANSIENT"] = Field(
        default="PERMANENT", description="The kind of database"
    )

    def get_core_object(self):
        return Database.from_dict(self.__dict__)

    def get_core_path(self, root: Root):
        # core_object = self.get_core_object()
        # if isinstance(core_object, Database):
        #     return root.databases
        # else:
        #     raise ValueError(f"Invalid object type: {self}")
        return root.databases


class SnowflakeSchema(ObjectMetadata):
    database_name: str = Field(description="The database the schema belongs to")
    kind: Literal["PERMANENT", "TRANSIENT"] = Field(
        default="PERMANENT", description="The kind of database"
    )

    def get_core_object(self):
        return Schema.from_dict(self.__dict__)

    def get_core_path(self, root: Root):
        # core_object = self.get_core_object()
        # if isinstance(core_object, Schema):
        #     return root.databases[self.database_name].schemas
        # else:
        #     raise ValueError(f"Invalid object type: {self}")
        return root.databases[self.database_name].schemas


class SnowflakeTableColumn(BaseModel):
    name: str = Field(description="The name of the column")
    datatype: str = Field(description="The data type of the column")


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

    def get_core_object(self):
        return Table.from_dict(self.__dict__)

    def get_core_path(self, root: Root):
        # core_object = self.get_core_object()
        # if isinstance(core_object, Table):
        #     return root.databases[self.database_name].schemas[self.schema_name].tables
        # else:
        #     raise ValueError(f"Invalid object type: {self}")
        root.databases[self.database_name].schemas[self.schema_name].tables


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
    auto_resume: bool = Field(
        default=None, description="Whether the warehouse is automatically resumed"
    )
    initially_suspended: bool = Field(
        default=None, description="Whether the warehouse is initially suspended"
    )

    def get_core_object(self):
        return Warehouse.from_dict(self.__dict__)

    def get_core_path(self, root: Root):
        # core_object = self.get_core_object()
        # if isinstance(core_object, Warehouse):
        #     return root.warehouses
        # else:
        #     raise ValueError(f"Invalid object type: {self}")
        return root.warehouses


SnowflakeClasses = [
    SnowflakeDatabase,
    SnowflakeSchema,
    SnowflakeTable,
    SnowflakeWarehouse,
]
