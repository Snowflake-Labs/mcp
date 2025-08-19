import json
from typing import Annotated, Any, Literal, Type

from fastmcp import FastMCP
from pydantic import Field
from snowflake.core import CreateMode, Root

from mcp_server_snowflake.object_manager.objects import (
    ObjectMetadata,
    SnowflakeClasses,
)
from mcp_server_snowflake.object_manager.prompts import (
    create_object_prompt,
    describe_object_prompt,
    drop_object_prompt,
    list_objects_prompt,
    update_object_prompt,
)
from mcp_server_snowflake.utils import SnowflakeException


def get_class_name(object_type: Any) -> str:
    return object_type.__class__.__name__.removesuffix("Model")


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
        core_path.create(core_object, mode=create_mode)
        return f"Created {get_class_name(core_object)} {core_object.name}."
    except Exception as e:
        raise SnowflakeException(tool="create_object", message=e)


def drop_object(object_type: ObjectMetadata, root: Root, if_exists: bool = False):
    core_object = object_type.get_core_object()
    core_path = object_type.get_core_path(root=root)
    try:
        core_path[core_object.name].drop(if_exists=if_exists)
        return f"Dropped {get_class_name(core_object)} {core_object.name}."
    except Exception as e:
        raise SnowflakeException(tool="drop_object", message=e)


def update_object(object_type: ObjectMetadata, root: Root):
    core_object = object_type.get_core_object()
    core_path = object_type.get_core_path(root=root)
    try:
        # First need to fetch the existing object
        existing_object = core_path[core_object.name].fetch()
        # Then update the existing object with the new properties
        for key, value in core_object.model_dump().items():
            if value is not None:
                setattr(existing_object, key, value)
        # Then create or alter the object
        core_path[core_object.name].create_or_alter(existing_object)
        return f"Updated {get_class_name(core_object)} {core_object.name}."

    except Exception as e:
        raise SnowflakeException(tool="update_object", message=e)


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
        # Try with limit first (works for most object types)
        try:
            return core_path.iter(like=like, limit=100)
        except TypeError:
            # Fall back to no limit for object types that don't support it (like warehouses)
            return core_path.iter(like=like)
    except Exception as e:
        raise SnowflakeException(tool="list_objects", message=e)


def parse_object(target_object: Any, obj_type: Type[ObjectMetadata], tool_name: str):
    """Parse a string into a Pydantic model.
    If the target_object is a string, parse it into a Pydantic model.
    If the target_object is already a Pydantic model, return it.
    This is to handle the case where the LLM passes the object as a JSON string.
    """
    if isinstance(target_object, str):
        try:
            parsed_data = json.loads(target_object)
            target_object = obj_type(**parsed_data)
        except Exception as e:
            raise SnowflakeException(tool=tool_name, message=e)

    return target_object


def initialize_object_manager_tools(server: FastMCP, root: Root):
    # Create a closure that captures the current object_type
    def create_tools_for_type(obj_type, obj_name):
        @server.tool(
            name=f"create_{obj_name}",
            description=create_object_prompt(obj_name),
        )
        def create_object_tool(
            # Allow both object and string inputs - Some LLMs still pass as JSON string
            target_object: Annotated[
                obj_type | str,
                Field(
                    description="Always pass properties of target_object as an object, not a string"
                ),
            ],
            mode: Literal[
                "error_if_exists", "replace", "if_not_exists"
            ] = "error_if_exists",
        ):
            # If string is passed, parse JSON and create object
            target_object = parse_object(target_object, obj_type, f"create_{obj_name}")
            return create_object(target_object, root, mode)

        @server.tool(
            name=f"drop_{obj_name}",
            description=drop_object_prompt(obj_name),
        )
        def drop_object_tool(
            target_object: Annotated[
                obj_type | str,
                Field(
                    description="Always pass properties of target_object as an object, not a string"
                ),
            ],
            if_exists: bool = False,
        ):
            target_object = parse_object(target_object, obj_type, f"drop_{obj_name}")
            drop_object(target_object, root, if_exists)
            return f"Dropped {obj_name} {target_object.name}."

        @server.tool(
            name=f"update_{obj_name}",
            description=update_object_prompt(obj_name),
        )
        def update_object_tool(
            target_object: Annotated[
                obj_type | str,
                Field(
                    description="Always pass properties of target_object as an object, not a string"
                ),
            ],
        ):
            target_object = parse_object(target_object, obj_type, f"update_{obj_name}")
            return update_object(target_object, root)

        @server.tool(
            name=f"describe_{obj_name}",
            description=describe_object_prompt(obj_name),
        )
        def describe_object_tool(
            target_object: Annotated[
                obj_type | str,
                Field(
                    description="Always pass properties of target_object as an object, not a string"
                ),
            ],
        ):
            target_object = parse_object(
                target_object, obj_type, f"describe_{obj_name}"
            )
            return describe_object(target_object, root)

        @server.tool(
            name=f"list_{obj_name}s",
            description=list_objects_prompt(obj_name),
        )
        def list_objects_tool(
            target_object: Annotated[
                obj_type | str,
                Field(
                    description="Always pass properties of target_object as an object, not a string"
                ),
            ],
            like: str | None = None,
        ):
            target_object = parse_object(target_object, obj_type, f"list_{obj_name}s")
            return list_objects(target_object, root, like)

    for object_type in SnowflakeClasses:
        object_name = object_type.__name__.lower().replace("snowflake", "")

        # Call the closure to create tools for this specific type
        create_tools_for_type(object_type, object_name)
