import json
from typing import Literal

from fastmcp import FastMCP
from snowflake.core import CreateMode, Root

from mcp_server_snowflake.object_manager.objects import (
    ObjectMetadata,
    SnowflakeClasses,
    SnowflakeWarehouse,
)
from mcp_server_snowflake.utils import SnowflakeException


def create_object(
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
    try:
        return core_path.create(core_object, mode=create_mode)
    except Exception as e:
        raise SnowflakeException(tool="create_object", message=e)


def drop_object(object_type: ObjectMetadata, root: Root, if_exists: bool = False):
    core_object = object_type.get_core_object()
    core_path = object_type.get_core_path(root=root)
    try:
        return core_path[core_object.name].drop(if_exists=if_exists)
    except Exception as e:
        raise SnowflakeException(tool="drop_object", message=e)


def describe_object(object_type: ObjectMetadata, root: Root):
    core_object = object_type.get_core_object()
    core_path = object_type.get_core_path(root=root)
    try:
        return core_path[core_object.name].fetch().to_dict()
    except Exception as e:
        raise SnowflakeException(tool="describe_object", message=e)


def list_objects(object_type: ObjectMetadata, root: Root, like: str = None):
    core_path = object_type.get_core_path(root=root)
    try:
        return core_path.iter(like=like, limit=100)
    except Exception as e:
        raise SnowflakeException(tool="list_objects", message=e)


def initialize_object_manager_tools(server: FastMCP, root: Root):
    for object_type in SnowflakeClasses:
        object_name = object_type.__name__.lower().replace("snowflake", "").lower()

        @server.tool(name=f"create_{object_name}")
        def create_object_tool(
            # fastMCP will automatically parse the input_schema from object_type Pydantic model from the request
            object_type: object_type,  # type: ignore
            mode: Literal[
                "error_if_exists", "replace", "if_not_exists"
            ] = "error_if_exists",
        ):
            return create_object(object_type, root, mode)

        @server.tool(name=f"drop_{object_name}")
        def drop_object_tool(
            object_type: object_type,  # type: ignore
            if_exists: bool = False,
        ):
            return drop_object(object_type, root, if_exists)

        @server.tool(name=f"describe_{object_name}")
        def describe_object_tool(
            object_type: object_type,  # type: ignore
        ):
            return describe_object(object_type, root)

        @server.tool(name=f"list_{object_name}s")
        def list_objects_tool(
            object_type: object_type,  # type: ignore
            like: str | None = None,
        ):
            return list_objects(object_type, root, like)

    @server.tool(name="hello world")
    def x(
        # fastMCP will automatically parse the input_schema from object_type Pydantic model from the request
        object_type: SnowflakeWarehouse | str,
        mode: Literal[
            "error_if_exists", "replace", "if_not_exists"
        ] = "error_if_exists",
    ):
        if isinstance(object_type, str):
            object_type = json.loads(object_type)
        return create_object(object_type, root, mode)
