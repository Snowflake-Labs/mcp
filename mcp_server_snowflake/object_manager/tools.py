import json
from typing import Annotated, Any, Literal, Union, get_args

from fastmcp import FastMCP
from pydantic import Field
from snowflake.core import CreateMode, Root

from mcp_server_snowflake.object_manager.objects import (
    SnowflakeComputePool,
    SnowflakeDatabase,
    SnowflakeImageRepository,
    SnowflakeObject,
    SnowflakeRole,
    SnowflakeSchema,
    SnowflakeStage,
    SnowflakeTable,
    SnowflakeUser,
    SnowflakeView,
    SnowflakeWarehouse,
    supported_objects,
)
from mcp_server_snowflake.object_manager.prompts import (
    get_object_mgmt_prompt,
)
from mcp_server_snowflake.utils import SnowflakeException, execute_query


def get_class_name(object_type: Any) -> str:
    return object_type.__class__.__name__.removesuffix("Model")


def create_object(
    snowflake_object: SnowflakeObject,
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
    core_object = snowflake_object.get_core_object()
    core_path = snowflake_object.get_core_path(root=root)
    try:
        core_path.create(core_object, mode=create_mode)
        return f"Created {get_class_name(core_object)} {core_object.name}."
    except Exception as e:
        raise SnowflakeException(tool="create_object", message=str(e))


def drop_object(snowflake_object: SnowflakeObject, root: Root, if_exists: bool = False):
    core_object = snowflake_object.get_core_object()
    core_path = snowflake_object.get_core_path(root=root)
    try:
        core_path[core_object.name].drop(if_exists=if_exists)
        return f"Dropped {get_class_name(core_object)} {core_object.name}."
    except Exception as e:
        raise SnowflakeException(tool="drop_object", message=str(e))


def create_or_alter_object(snowflake_object: SnowflakeObject, root: Root):
    core_object = snowflake_object.get_core_object()
    core_path = snowflake_object.get_core_path(root=root)
    try:
        # First need to fetch the existing object
        existing_object = core_path[core_object.name].fetch()

        # Then update the existing object with the new properties
        data = snowflake_object.model_dump(exclude_unset=True)
        # Update only non-None values
        for key, value in data.items():
            if value is not None and hasattr(existing_object, key):
                setattr(existing_object, key, value)
        # Then create or alter the object
        core_path[core_object.name].create_or_alter(existing_object)
        return f"Created or altered {get_class_name(core_object)} {core_object.name}."

    except Exception as e:
        raise SnowflakeException(tool="create_or_alter_object", message=str(e))


def describe_object(snowflake_object: SnowflakeObject, root: Root):
    core_object = snowflake_object.get_core_object()
    core_path = snowflake_object.get_core_path(root=root)
    try:
        return core_path[core_object.name].fetch().to_dict()
    except Exception as e:
        raise SnowflakeException(tool="describe_object", message=str(e))


def list_objects(
    snowflake_service,
    object_type: supported_objects,
    database_name: str = None,
    schema_name: str = None,
    like: str = None,
    starts_with: str = None,
):
    if object_type == "image_repository":
        object_name = "image repositories"
    elif object_type == "compute_pool":
        object_name = "compute pools"
    else:
        object_name = f"{object_type}s"

    statement = f"SHOW {object_name}"

    if like:
        statement += f" LIKE '%{like.replace('%', '')}%'"

    if object_type in ["database", "compute_pool", "role", "user"]:
        pass
    elif database_name is None and schema_name is None:
        statement += " IN ACCOUNT"
    elif database_name and schema_name:
        statement += f" IN SCHEMA {database_name}.{schema_name}"
    elif database_name:
        statement += f" IN DATABASE {database_name}"
    elif schema_name:
        statement += f" IN SCHEMA {schema_name}"
    else:
        raise SnowflakeException(
            tool="list_objects",
            message="Please specify a database, database + schema, or neither to query the account.",
        )

    if starts_with:
        statement += f" STARTS WITH '{starts_with}'"

    try:
        result = execute_query(statement, snowflake_service)

        if len(result) > 0:
            return result[0:1000]  # Limit to 1000 results
        else:
            return f"No matching {object_name} found."
    except Exception as e:
        raise SnowflakeException(tool="list_semantic_views", message=str(e))


def parse_object(target_object: Any, obj_type: supported_objects):
    """Parse a string into a Pydantic model.
    If the target_object is a string, parse it into a Pydantic model.
    If the target_object is already a Pydantic model, return it.
    This is to handle the case where the LLM passes the object as a JSON string.
    """
    if isinstance(target_object, str):
        try:
            if obj_type == "database":
                obj_type = SnowflakeDatabase
            elif obj_type == "schema":
                obj_type = SnowflakeSchema
            elif obj_type == "table":
                obj_type = SnowflakeTable
            elif obj_type == "view":
                obj_type = SnowflakeView
            elif obj_type == "warehouse":
                obj_type = SnowflakeWarehouse
            elif obj_type == "compute_pool":
                obj_type = SnowflakeComputePool
            elif obj_type == "role":
                obj_type = SnowflakeRole
            elif obj_type == "stage":
                obj_type = SnowflakeStage
            elif obj_type == "user":
                obj_type = SnowflakeUser
            elif obj_type == "image_repository":
                obj_type = SnowflakeImageRepository
            else:
                raise ValueError(f"Invalid object type: {obj_type}")
            parsed_data = json.loads(target_object)
            return obj_type(**parsed_data)
        except Exception as e:
            raise e
    else:
        return target_object


def initialize_object_manager_tools(server: FastMCP, snowflake_service):
    root = snowflake_service.root
    supported_objects_list = list(get_args(supported_objects))
    object_type_annotation = Annotated[
        supported_objects,
        Field(
            description=f"Type of Snowflake object. One of {', '.join(supported_objects_list)}"
        ),
    ]
    # Extract union members from SnowflakeObject TypeAlias for Pydantic schema generation
    # (TypeAlias doesn't work well with FastMCP/Pydantic v2, but explicit Union does)
    target_object_annotation = Annotated[
        Union[
            str, *get_args(SnowflakeObject)
        ],  # Allow both object and string inputs - Some LLMs still pass as JSON string
        Field(
            description="Always pass properties of target_object as an object, not a string"
        ),
    ]

    @server.tool(
        name="create_object",
        description=get_object_mgmt_prompt("create", supported_objects_list),
    )
    def create_object_tool(
        object_type: object_type_annotation,
        target_object: target_object_annotation,
        mode: Literal[
            "error_if_exists", "replace", "if_not_exists"
        ] = "error_if_exists",
    ):
        # If string is passed, parse JSON and create object
        target_object = parse_object(target_object, object_type)
        return create_object(target_object, root, mode)

    @server.tool(
        name="drop_object",
        description=get_object_mgmt_prompt("drop", supported_objects_list),
    )
    def drop_object_tool(
        object_type: object_type_annotation,
        target_object: target_object_annotation,
        if_exists: bool = False,
    ):
        target_object = parse_object(target_object, object_type)
        return drop_object(target_object, root, if_exists)

    @server.tool(
        name="create_or_alter_object",
        description=get_object_mgmt_prompt("create_or_alter", supported_objects_list),
    )
    def create_or_alter_object_tool(
        object_type: object_type_annotation,
        target_object: target_object_annotation,
    ):
        target_object = parse_object(target_object, object_type)
        return create_or_alter_object(target_object, root)

    @server.tool(
        name="describe_object",
        description=get_object_mgmt_prompt("describe", supported_objects_list),
    )
    def describe_object_tool(
        object_type: object_type_annotation,
        target_object: target_object_annotation,
    ):
        target_object = parse_object(target_object, object_type)
        return describe_object(target_object, root)

    @server.tool(
        name="list_objects",
        description=get_object_mgmt_prompt("list", supported_objects_list),
    )
    def list_objects_tool(
        object_type: object_type_annotation,
        database_name: str | None = None,
        schema_name: str | None = None,
        like: Annotated[
            str | None,
            Field(
                description="Filter objects by keyword in name. Uses case-insensitive pattern matching, with support for SQL wildcard characters (% and _).",
                default=None,
            ),
        ] = None,
        starts_with: Annotated[
            str | None,
            Field(
                description="Filter objects by start of name. Case sensitive. Ignored for warehouses.",
                default=None,
            ),
        ] = None,
    ):
        return list_objects(
            snowflake_service,
            object_type,
            database_name,
            schema_name,
            like,
            starts_with,
        )


def validate_object_tool(
    function_name: str, sql_allow_list: list[str], sql_disallow_list: list[str]
) -> tuple[str, bool]:
    """
    Validates a function call against a list of allowed and disallowed object types.

    Only consider some object actions for now including create, create_or_alter, and drop.
    """
    if function_name.lower().startswith(
        "create"
    ):  # Will also capture create_or_alter, which is intended
        func_type = "create"
    elif function_name.lower().startswith("drop"):
        func_type = "drop"
    else:
        return ("", True)

    # User has not added any permissions, so we default to disallowing all object actions
    if len(sql_allow_list) == 0 and len(sql_disallow_list) == 0:
        valid = False

    if func_type in sql_allow_list:
        valid = True
    elif func_type in sql_disallow_list:
        valid = False
    else:
        valid = False

    return (func_type, valid)
