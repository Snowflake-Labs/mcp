from typing import Annotated, Literal

from fastmcp import FastMCP
from pydantic import Field

from mcp_server_snowflake.semantic_manager.objects import SemanticExpression
from mcp_server_snowflake.semantic_manager.prompts import (
    query_semantic_view_prompt,
    write_semantic_view_query_prompt,
)
from mcp_server_snowflake.utils import SnowflakeException, execute_query


def list_semantic_views(
    snowflake_service,
    database_name: str = None,
    schema_name: str = None,
    like: str = None,
    starts_with: str = None,
):
    statement = "SHOW SEMANTIC VIEWS"

    if like:
        statement += f" LIKE '%{like.replace('%', '')}%'"

    if not database_name and not schema_name:
        statement += " IN ACCOUNT"
    elif database_name and schema_name:
        statement += f" IN SCHEMA {database_name}.{schema_name}"
    elif database_name:
        statement += f" IN DATABASE {database_name}"
    elif schema_name:
        statement += f" IN SCHEMA {schema_name}"
    else:
        raise SnowflakeException(
            tool="list_semantic_views",
            message="Please specify a database, database + schema, or neither to query the account.",
        )

    if starts_with:
        statement += f" STARTS WITH '{starts_with}'"

    try:
        result = execute_query(statement, snowflake_service)
        # Semantic view metadata has unnecessary extension key
        for item in result:
            item.pop("extension", None)
        return result
    except Exception as e:
        raise SnowflakeException(tool="list_semantic_views", message=str(e))


def describe_semantic_view(
    snowflake_service, view_name: str, database_name: str, schema_name: str
):
    if not database_name and not schema_name:
        raise SnowflakeException(
            tool="describe_semantic_view", message="Please specify a database + schema."
        )
    if not view_name:
        raise SnowflakeException(
            tool="describe_semantic_view", message="Please specify a view name."
        )

    statement = f"DESCRIBE SEMANTIC VIEW {database_name}.{schema_name}.{view_name}"

    try:
        result = execute_query(statement, snowflake_service)
        # Semantic view metadata has ugly extension key, so we need to remove it
        result = [item for item in result if item.get("object_kind") != "EXTENSION"]
        return result
    except Exception as e:
        raise SnowflakeException(tool="list_semantic_views", message=str(e))


def show_semantic_expressions(
    snowflake_service,
    expression_type: Literal["DIMENSIONS", "METRICS"] = "DIMENSIONS",
    database_name: str = None,
    schema_name: str = None,
    view_name: str = None,
    like: str = None,
    starts_with: str = None,
):
    statement = f"SHOW SEMANTIC {expression_type}"

    if like:
        statement += f" LIKE '%{like.replace('%', '')}%'"

    if view_name:
        statement += " IN"
    elif schema_name:
        statement += " IN SCHEMA"
    elif database_name:
        statement += " IN DATABASE"
    else:
        statement += " IN ACCOUNT"

    if database_name:
        statement += f" {database_name}"
    if schema_name:
        statement += f".{schema_name}"
    if view_name:
        statement += f".{view_name}"

    if starts_with:
        statement += f" STARTS WITH '{starts_with}'"

    try:
        result = execute_query(statement, snowflake_service)
        if not result:
            return f"No {expression_type.lower()} found."
        return result
    except Exception as e:
        raise SnowflakeException(tool="show_semantic_dimensions", message=str(e))


def get_semantic_view_ddl(
    snowflake_service, view_name: str, database_name: str, schema_name: str
):
    if not database_name and not schema_name:
        raise SnowflakeException(
            tool="get_semantic_view_ddl", message="Please specify a database + schema."
        )
    if not view_name:
        raise SnowflakeException(
            tool="get_semantic_view_ddl", message="Please specify a view name."
        )

    statement = f"SELECT GET_DDL('SEMANTIC_VIEW', '{database_name}.{schema_name}.{view_name}', TRUE) as DDL"

    try:
        return execute_query(statement, snowflake_service)[0].get("DDL")
    except Exception as e:
        raise SnowflakeException(tool="get_semantic_view_ddl", message=str(e))


def write_semantic_view_query(
    view_name: str,
    database_name: str,
    schema_name: str,
    dimensions: list[SemanticExpression] = [],
    metrics: list[SemanticExpression] = [],
    facts: list[SemanticExpression] = [],
    where_clause: str = None,
    order_by: str = None,
    limit: int | str = None,
):
    """
    Query a semantic view with comprehensive support for all SEMANTIC_VIEW clauses.

    Based on Snowflake documentation: https://docs.snowflake.com/en/user-guide/views-semantic/querying

    Validation rules:
    - Must specify at least one of DIMENSIONS, METRICS, or FACTS
    - Cannot specify both FACTS and METRICS in the same query
    - When using FACTS + DIMENSIONS, all must be from the same logical table
    """

    # Validation: Ensure at least one clause is specified
    if not dimensions and not metrics and not facts:
        raise SnowflakeException(
            tool="write_semantic_view_query",
            message="Must specify at least one of DIMENSIONS, METRICS, or FACTS",
        )

    # Validation: Cannot use FACTS and METRICS together
    if facts and metrics:
        raise SnowflakeException(
            tool="write_semantic_view_query",
            message="Cannot specify both FACTS and METRICS in the same SEMANTIC_VIEW query",
        )

    statement = f"""SELECT * FROM SEMANTIC_VIEW (
        {database_name}.{schema_name}.{view_name}
    """

    # Add clauses in order (affects output column order)
    if dimensions:
        statement += f" DIMENSIONS {', '.join([f'{expr.table}.{expr.name}' for expr in dimensions])}"

    if metrics:
        statement += (
            f" METRICS {', '.join([f'{expr.table}.{expr.name}' for expr in metrics])}"
        )

    if facts:
        statement += (
            f" FACTS {', '.join([f'{expr.table}.{expr.name}' for expr in facts])}"
        )

    statement += ")"  # Close out the semantic sub-select

    # Add optional clauses
    if where_clause:
        statement += f" WHERE {where_clause}"

    if order_by:
        statement += f" ORDER BY {order_by}"

    if limit:
        statement += f" LIMIT {int(limit)}"

    try:
        return statement
    except Exception as e:
        raise SnowflakeException(tool="write_semantic_view_query", message=str(e))


def query_semantic_view(
    snowflake_service,
    view_name: str,
    database_name: str,
    schema_name: str,
    dimensions: list[SemanticExpression] = [],
    metrics: list[SemanticExpression] = [],
    facts: list[SemanticExpression] = [],
    where_clause: str = None,
    order_by: str = None,
    limit: int | str = None,
):
    try:
        statement = write_semantic_view_query(
            view_name,
            database_name,
            schema_name,
            dimensions,
            metrics,
            facts,
            where_clause,
            order_by,
            limit,
        )

        return execute_query(statement, snowflake_service)
    except Exception as e:
        raise SnowflakeException(tool="query_semantic_view", message=str(e))


def validate_semantic_view_tool(
    function_name: str,
    sql_allow_list: list[str],
    sql_disallow_list: list[str],
):
    if function_name.lower().startswith("list"):
        func_type = "select"
    else:  # All other semantic view tools are permissible
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


def initialize_semantic_manager_tools(server: FastMCP, snowflake_service):
    @server.tool(
        name="list_semantic_views",
        description="List all semantic views in the account, database, or schema.",
    )
    def list_semantic_views_tool(
        database_name: Annotated[
            str | None,
            Field(
                description="The name of the database to list semantic views in. Omit to query account.",
                default=None,
            ),
        ],
        schema_name: Annotated[
            str | None,
            Field(
                description="The name of the schema to list semantic views in. Omit to query account.",
                default=None,
            ),
        ],
        like: Annotated[
            str | None,
            Field(
                description="Filter semantic views by keyword in name. Case insensitive.",
                default=None,
            ),
        ],
        starts_with: Annotated[
            str | None,
            Field(
                description="Filter semantic views by start of name. Case sensitive.",
                default=None,
            ),
        ],
    ):
        return list_semantic_views(
            snowflake_service, database_name, schema_name, like, starts_with
        )

    @server.tool(
        name="describe_semantic_view",
        description="Describe a semantic view.",
    )
    def describe_semantic_view_tool(
        view_name: Annotated[
            str, Field(description="The name of the semantic view to describe.")
        ],
        database_name: Annotated[
            str,
            Field(
                description="The name of the database to describe the semantic view in."
            ),
        ],
        schema_name: Annotated[
            str,
            Field(
                description="The name of the schema to describe the semantic view in."
            ),
        ],
    ):
        return describe_semantic_view(
            snowflake_service, view_name, database_name, schema_name
        )

    @server.tool(
        name="show_semantic_dimensions",
        description="Show all semantic dimensions in the account, database, or schema.",
    )
    def show_semantic_dimensions_tool(
        database_name: Annotated[
            str,
            Field(
                description="The name of the database to show semantic dimensions in."
            ),
        ],
        schema_name: Annotated[
            str,
            Field(description="The name of the schema to show semantic dimensions in."),
        ],
        view_name: Annotated[
            str,
            Field(description="The name of the semantic view to show dimensions in."),
        ],
        like: Annotated[
            str | None,
            Field(
                description="Filter semantic views by keyword in name. Case insensitive.",
                default=None,
            ),
        ],
        starts_with: Annotated[
            str | None,
            Field(
                description="Filter semantic views by start of name. Case sensitive.",
                default=None,
            ),
        ],
    ):
        return show_semantic_expressions(
            snowflake_service,
            "DIMENSIONS",
            database_name,
            schema_name,
            view_name,
            like,
            starts_with,
        )

    @server.tool(
        name="show_semantic_metrics",
        description="Show all semantic metrics in the account, database, or schema.",
    )
    def show_semantic_metrics_tool(
        database_name: Annotated[
            str,
            Field(description="The name of the database to show semantic metrics in."),
        ],
        schema_name: Annotated[
            str,
            Field(description="The name of the schema to show semantic metrics in."),
        ],
        view_name: Annotated[
            str, Field(description="The name of the semantic view to show metrics in.")
        ],
        like: Annotated[
            str | None,
            Field(
                description="Filter semantic views by keyword in name. Case insensitive.",
                default=None,
            ),
        ],
        starts_with: Annotated[
            str | None,
            Field(
                description="Filter semantic views by start of name. Case sensitive.",
                default=None,
            ),
        ],
    ):
        return show_semantic_expressions(
            snowflake_service,
            "METRICS",
            database_name,
            schema_name,
            view_name,
            like,
            starts_with,
        )

    @server.tool(
        name="get_semantic_view_ddl",
        description="Get the DDL for a semantic view.",
    )
    def get_semantic_view_ddl_tool(
        database_name: Annotated[
            str,
            Field(
                description="The name of the database to get the DDL for the semantic view in."
            ),
        ],
        schema_name: Annotated[
            str,
            Field(
                description="The name of the schema to get the DDL for the semantic view in."
            ),
        ],
        view_name: Annotated[
            str, Field(description="The name of the semantic view to get the DDL for.")
        ],
    ):
        return get_semantic_view_ddl(
            snowflake_service, view_name, database_name, schema_name
        )

    @server.tool(
        name="write_semantic_view_query_tool",
        description=write_semantic_view_query_prompt,
    )
    def write_semantic_view_tool(
        database_name: Annotated[
            str,
            Field(description="The name of the database containing the semantic view."),
        ],
        schema_name: Annotated[
            str,
            Field(description="The name of the schema containing the semantic view."),
        ],
        view_name: Annotated[
            str, Field(description="The name of the semantic view to query.")
        ],
        dimensions: Annotated[
            list[SemanticExpression],
            Field(
                description="List of dimensions to include in the query. Each dimension should specify table and name/expression.",
                default_factory=list,
            ),
        ],
        metrics: Annotated[
            list[SemanticExpression],
            Field(
                description="List of metrics to include in the query. Each metric should specify table and name. Cannot be used with facts.",
                default_factory=list,
            ),
        ],
        facts: Annotated[
            list[SemanticExpression],
            Field(
                description="List of facts to include in the query. Each fact should specify table and name. Cannot be used with metrics.",
                default_factory=list,
            ),
        ],
        where_clause: Annotated[
            str | None,
            Field(
                description="Optional WHERE clause conditions (without the WHERE keyword).",
                default=None,
            ),
        ],
        order_by: Annotated[
            str | None,
            Field(
                description="Optional ORDER BY clause (without the ORDER BY keywords).",
                default=None,
            ),
        ],
        limit: Annotated[
            int | str | None,
            Field(
                description="Optional LIMIT for number of rows to return.", default=None
            ),
        ],
    ):
        return write_semantic_view_query(
            view_name,
            database_name,
            schema_name,
            dimensions,
            metrics,
            facts,
            where_clause,
            order_by,
            limit,
        )

    @server.tool(
        name="query_semantic_view",
        description=query_semantic_view_prompt,
    )
    def query_semantic_view_tool(
        database_name: Annotated[
            str,
            Field(description="The name of the database containing the semantic view."),
        ],
        schema_name: Annotated[
            str,
            Field(description="The name of the schema containing the semantic view."),
        ],
        view_name: Annotated[
            str, Field(description="The name of the semantic view to query.")
        ],
        dimensions: Annotated[
            list[SemanticExpression],
            Field(
                description="List of dimensions to include in the query. Each dimension should specify table and name/expression.",
                default_factory=list,
            ),
        ],
        metrics: Annotated[
            list[SemanticExpression],
            Field(
                description="List of metrics to include in the query. Each metric should specify table and name. Cannot be used with facts.",
                default_factory=list,
            ),
        ],
        facts: Annotated[
            list[SemanticExpression],
            Field(
                description="List of facts to include in the query. Each fact should specify table and name. Cannot be used with metrics.",
                default_factory=list,
            ),
        ],
        where_clause: Annotated[
            str | None,
            Field(
                description="Optional WHERE clause conditions (without the WHERE keyword).",
                default=None,
            ),
        ],
        order_by: Annotated[
            str | None,
            Field(
                description="Optional ORDER BY clause (without the ORDER BY keywords).",
                default=None,
            ),
        ],
        limit: Annotated[
            int | str | None,
            Field(
                description="Optional LIMIT for number of rows to return.", default=None
            ),
        ],
    ):
        return query_semantic_view(
            snowflake_service,
            view_name,
            database_name,
            schema_name,
            dimensions,
            metrics,
            facts,
            where_clause,
            order_by,
            limit,
        )
