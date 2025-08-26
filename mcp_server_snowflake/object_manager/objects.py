from typing import Literal

from pydantic import BaseModel, Field
from snowflake.core import CreateMode, Root
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


async def create_object(
    object_type: ObjectMetadata,
    root: Root,
    mode: Literal["error_if_exists", "replace", "if_not_exists"] = "error_if_exists",
):
    if mode == "error_if_exists":
        create_mode = CreateMode.error_if_exists
    elif mode == "replace":
        create_mode = CreateMode.or_replace
    elif mode == "if_not_exists":
        create_mode = CreateMode.if_not_exists
    else:
        create_mode = CreateMode.if_not_exists
    core_object = object_type.get_core_object()
    core_path = object_type.get_core_path(root=root)
    return core_path.create(core_object, mode=create_mode)


def drop_object(object_type: ObjectMetadata, root: Root, if_exists: bool = False):
    core_object = object_type.get_core_object()
    core_path = object_type.get_core_path(root=root)
    return core_path[core_object.name].drop(if_exists=if_exists)


# TODOS:
# - How to integrate optional params like CreateMode into create and if_exists into drop?
# - Add additional assertions at the class level if possible
