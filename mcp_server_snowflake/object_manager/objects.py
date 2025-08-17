from typing import Literal

from pydantic import BaseModel, Field
from snowflake.core import Root
from snowflake.core.database import Database
from snowflake.core.schema import Schema


class ObjectMetadata(BaseModel):
    name: str = Field(description="The name of the object")
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
        core_object = self.get_core_object()
        if isinstance(core_object, Database):
            return root.databases
        else:
            raise ValueError(f"Invalid object type: {self}")


class SnowflakeSchema(ObjectMetadata):
    database_name: str = Field(description="The database the schema belongs to")
    kind: Literal["PERMANENT", "TRANSIENT"] = Field(
        default="PERMANENT", description="The kind of database"
    )

    def get_core_object(self):
        return Schema.from_dict(self.__dict__)

    def get_core_path(self, root: Root):
        core_object = self.get_core_object()
        if isinstance(core_object, Schema):
            return root.databases[self.database_name].schemas
        else:
            raise ValueError(f"Invalid object type: {self}")


SnowflakeClasses = [SnowflakeDatabase, SnowflakeSchema]


# TODOS:
# - Add additional assertions at the class level if possible
